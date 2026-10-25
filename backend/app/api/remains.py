from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.mortuary import CustodyEvent, MortuaryBelonging, RemainsRecord
from app.models.resource import Resource
from app.schemas.mortuary import (
    CustodyEventCreate,
    MortuaryBelongingCreate,
    MortuaryBelongingReturn,
    MortuaryBelongingResponse,
    MortuaryBelongingTransfer,
    MortuaryBelongingUpdate,
    RemainsCreate,
    RemainsDetail,
    RemainsUpdate,
    ReleaseRequest,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.mortuary import (
    MortuaryError,
    cooling_status,
    default_tag,
    get_placeable_location,
    is_cold,
    now_utc,
    deceased_identifier_matches,
    release_blockers,
)
from app.services.mortuary_alerts import tell_operations
from app.services.permission_service import has_permission


router = APIRouter(
    prefix="/cases",
    tags=["Remains and custody"],
)


AUDITED_REMAINS_FIELDS = (
    "received_from_type",
    "received_from",
    "collected_by_name",
    "vehicle_resource_id",
    "condition_notes",
    "belongings",
)

# How far in the future a time may be before it is clearly a mistake.
CLOCK_ALLOWANCE = timedelta(minutes=5)


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def get_user_id(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


def get_case(
    db: Session,
    case_id: UUID,
    business_id: UUID,
    *,
    for_change: bool = False,
) -> FuneralCase:
    query = db.query(FuneralCase).filter(
        FuneralCase.id == case_id,
        FuneralCase.business_id == business_id,
    )

    if for_change:
        query = query.with_for_update()

    case = query.first()

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    if for_change and case.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived cases cannot be changed. Restore it first.",
        )

    return case


def get_remains(
    db: Session,
    case_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> RemainsRecord:
    query = db.query(RemainsRecord).filter(
        RemainsRecord.case_id == case_id,
        RemainsRecord.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    remains = query.first()

    if remains is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No remains have been taken into care for this case",
        )

    return remains


def get_open_remains(
    db: Session,
    case_id: UUID,
    business_id: UUID,
) -> RemainsRecord:
    """The remains, locked, and still in our care."""

    remains = get_remains(db, case_id, business_id, lock=True)

    if remains.status == "released":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "These remains have been released. The custody log "
                "is closed."
            ),
        )

    return remains


def raise_mortuary_error(db: Session, error: MortuaryError):
    db.rollback()

    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


def as_utc(value: datetime | None) -> datetime | None:
    """A time with no zone is taken to be UTC."""

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def check_time(
    value: datetime | None,
    *,
    earliest: datetime | None = None,
    label: str = "The time",
) -> datetime:
    """A usable time: given or now, never in the future, and never
    before the remains arrived."""

    value = as_utc(value) or now_utc()

    if value > now_utc() + CLOCK_ALLOWANCE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{label} cannot be in the future",
        )

    if earliest is not None and value < earliest:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{label} cannot be before the remains arrived",
        )

    return value


def log_event(
    db: Session,
    *,
    remains: RemainsRecord,
    event_type: str,
    occurred_at: datetime,
    performed_by: UUID,
    from_location_id: UUID | None = None,
    to_location_id: UUID | None = None,
    handed_over_by_name: str | None = None,
    accepted_by_name: str | None = None,
    procedure: str | None = None,
    temperature_c=None,
    notes: str | None = None,
) -> CustodyEvent:
    event = CustodyEvent(
        business_id=remains.business_id,
        remains_id=remains.id,
        event_type=event_type,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        handed_over_by_name=handed_over_by_name,
        accepted_by_name=accepted_by_name,
        procedure=procedure,
        temperature_c=temperature_c,
        performed_by=performed_by,
        occurred_at=occurred_at,
        notes=notes,
    )

    db.add(event)

    return event


def audit_remains(
    db: Session,
    *,
    remains: RemainsRecord,
    case: FuneralCase,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    create_audit_log(
        db,
        business_id=remains.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="remains",
        entity_id=remains.id,
        details={
            "case_id": str(case.id),
            "case_number": case.case_number,
            "tag_number": remains.tag_number,
            **(extra or {}),
        },
        notes=notes,
    )


def build_detail(
    db: Session,
    remains: RemainsRecord,
) -> dict:
    events = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.remains_id == remains.id)
        .order_by(CustodyEvent.occurred_at, CustodyEvent.created_at)
        .all()
    )

    blockers: list[str] = []

    if remains.status == "in_custody":
        death_record = (
            db.query(DeathRecord)
            .filter(DeathRecord.case_id == remains.case_id)
            .first()
        )

        items = (
            db.query(CasePaperworkItem)
            .filter(CasePaperworkItem.case_id == remains.case_id)
            .all()
        )

        blockers = release_blockers(
            remains=remains,
            death_record=death_record,
            paperwork_items=items,
        )

    return {
        "remains": remains,
        "cooling": cooling_status(remains),
        "release_blockers": blockers,
        "events": events,
    }


# ============================================================
# TAKE INTO CARE
# ============================================================

@router.post(
    "/{case_id}/remains",
    response_model=RemainsDetail,
    status_code=status.HTTP_201_CREATED,
)
def take_into_care(
    case_id: UUID,
    data: RemainsCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)

    existing = (
        db.query(RemainsRecord.id)
        .filter(RemainsRecord.case_id == case.id)
        .first()
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has a custody record",
        )

    received_at = check_time(data.received_at, label="The arrival time")

    if data.vehicle_resource_id is not None:
        vehicle = (
            db.query(Resource.id)
            .filter(
                Resource.id == data.vehicle_resource_id,
                Resource.business_id == business_id,
                Resource.resource_type == "vehicle",
            )
            .first()
        )

        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Vehicle not found",
            )

    location = None

    if data.location_id is not None:
        try:
            location = get_placeable_location(
                db, business_id, data.location_id
            )
        except MortuaryError as error:
            raise_mortuary_error(db, error)

    remains = RemainsRecord(
        business_id=business_id,
        case_id=case.id,
        tag_number=data.tag_number or default_tag(case.case_number),
        status="in_custody",
        received_at=received_at,
        received_from_type=data.received_from_type,
        received_from=data.received_from,
        collected_by_name=data.collected_by_name,
        vehicle_resource_id=data.vehicle_resource_id,
        condition_notes=data.condition_notes,
        belongings=data.belongings,
        current_location_id=location.id if location else None,
        cooled_at=received_at if is_cold(location) else None,
        received_by=get_user_id(current_user),
    )

    db.add(remains)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That tag number is already in use",
        )

    log_event(
        db,
        remains=remains,
        event_type="received",
        occurred_at=received_at,
        performed_by=get_user_id(current_user),
        to_location_id=remains.current_location_id,
    )

    audit_remains(
        db,
        remains=remains,
        case=case,
        current_user=current_user,
        action="remains.received",
        notes="Remains were taken into care.",
        extra={
            "received_from_type": remains.received_from_type,
            "location_id": (
                str(location.id) if location else None
            ),
        },
    )

    tell_operations(
        db,
        business_id=business_id,
        title=f"{case.deceased_full_name} was taken into the mortuary",
        body=f"Tag {remains.tag_number}",
        link=f"/cases/{case.id}",
        actor_id=get_user_id(current_user),
    )

    db.commit()
    db.refresh(remains)

    return build_detail(db, remains)


# ============================================================
# READ
# ============================================================

@router.get(
    "/{case_id}/remains",
    response_model=RemainsDetail,
)
def read_remains(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.view")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id)

    return build_detail(db, get_remains(db, case.id, business_id))


# ============================================================
# UPDATE THE RECORD
# ============================================================

@router.patch(
    "/{case_id}/remains",
    response_model=RemainsDetail,
)
def update_remains(
    case_id: UUID,
    data: RemainsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_open_remains(db, case.id, business_id)

    updates = data.model_dump(exclude_unset=True)

    if updates.get("received_from_type", "") is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="received_from_type cannot be null",
        )

    vehicle_id = updates.get("vehicle_resource_id")

    if vehicle_id is not None:
        vehicle = (
            db.query(Resource.id)
            .filter(
                Resource.id == vehicle_id,
                Resource.business_id == business_id,
                Resource.resource_type == "vehicle",
            )
            .first()
        )

        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Vehicle not found",
            )

    old_values = snapshot_fields(remains, AUDITED_REMAINS_FIELDS)

    for field, value in updates.items():
        setattr(remains, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(remains, AUDITED_REMAINS_FIELDS),
    )

    if changes:
        audit_remains(
            db,
            remains=remains,
            case=case,
            current_user=current_user,
            action="remains.updated",
            notes="Remains record was updated.",
            extra={"changes": changes},
        )

    db.commit()
    db.refresh(remains)

    return build_detail(db, remains)


# ============================================================
# CUSTODY EVENTS
# ============================================================

@router.post(
    "/{case_id}/remains/events",
    response_model=RemainsDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_custody_event(
    case_id: UUID,
    data: CustodyEventCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_open_remains(db, case.id, business_id)

    occurred_at = check_time(
        data.occurred_at,
        earliest=remains.received_at,
    )

    user_id = get_user_id(current_user)
    kind = data.event_type
    extra: dict = {}

    if kind == "moved":
        if data.to_location_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Choose where the remains are being moved to",
            )

        if remains.current_location_id == data.to_location_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The remains are already there",
            )

        try:
            target = get_placeable_location(
                db, business_id, data.to_location_id
            )
        except MortuaryError as error:
            raise_mortuary_error(db, error)

        if not data.handed_over_by_name or not data.accepted_by_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Record the name of the person handing over "
                    "and the person accepting custody"
                ),
            )

        previous = remains.current_location_id
        remains.current_location_id = target.id

        if remains.cooled_at is None and is_cold(target):
            remains.cooled_at = occurred_at

        log_event(
            db,
            remains=remains,
            event_type="moved",
            occurred_at=occurred_at,
            performed_by=user_id,
            from_location_id=previous,
            to_location_id=target.id,
            handed_over_by_name=data.handed_over_by_name,
            accepted_by_name=data.accepted_by_name,
            notes=data.notes,
        )

        action = "remains.moved"
        text = "Remains were moved."
        extra = {
            "from_location_id": str(previous) if previous else None,
            "to_location_id": str(target.id),
            "handed_over_by_name": data.handed_over_by_name,
            "accepted_by_name": data.accepted_by_name,
        }

    elif kind == "prepared":
        if data.procedure is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Say what was done to the remains",
            )

        log_event(
            db,
            remains=remains,
            event_type="prepared",
            occurred_at=occurred_at,
            performed_by=user_id,
            procedure=data.procedure,
            notes=data.notes,
        )

        action = "remains.prepared"
        text = "Remains were prepared."
        extra = {"procedure": data.procedure}

    elif kind == "identified":
        if not data.identified_by_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Say who identified the remains",
            )

        if remains.identified_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The remains were already identified. Add a note "
                    "if something needs correcting."
                ),
            )

        remains.identified_at = occurred_at
        remains.identified_by_name = data.identified_by_name
        remains.identified_relationship = data.identified_relationship

        log_event(
            db,
            remains=remains,
            event_type="identified",
            occurred_at=occurred_at,
            performed_by=user_id,
            notes=data.notes,
        )

        action = "remains.identified"
        text = "Remains were formally identified."

    elif kind == "temperature":
        if data.temperature_c is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Enter the temperature",
            )

        log_event(
            db,
            remains=remains,
            event_type="temperature",
            occurred_at=occurred_at,
            performed_by=user_id,
            temperature_c=data.temperature_c,
            notes=data.notes,
        )

        action = "remains.temperature_logged"
        text = "A temperature was recorded."
        extra = {"temperature_c": str(data.temperature_c)}

    else:
        if not data.notes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Write the note",
            )

        log_event(
            db,
            remains=remains,
            event_type="note",
            occurred_at=occurred_at,
            performed_by=user_id,
            notes=data.notes,
        )

        action = "remains.note_added"
        text = "A note was added to the custody log."

    audit_remains(
        db,
        remains=remains,
        case=case,
        current_user=current_user,
        action=action,
        notes=text,
        extra=extra,
    )

    db.commit()
    db.refresh(remains)

    return build_detail(db, remains)


# ============================================================
# RELEASE
# ============================================================

@router.post(
    "/{case_id}/remains/release",
    response_model=RemainsDetail,
)
def release_remains(
    case_id: UUID,
    data: ReleaseRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.release")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_open_remains(db, case.id, business_id)

    user_id = get_user_id(current_user)

    # The tag is checked first and can never be overridden. A wrong
    # tag is recorded, because a near-miss is worth knowing about.
    if (
        data.confirm_tag_number.strip().casefold()
        != remains.tag_number.casefold()
    ):
        audit_remains(
            db,
            remains=remains,
            case=case,
            current_user=current_user,
            action="remains.release_refused",
            notes="Release was refused: the tag number did not match.",
            extra={"reason": "tag_mismatch"},
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "That tag number does not match these remains. "
                "Check you have the right remains."
            ),
        )

    death_record = (
        db.query(DeathRecord)
        .filter(DeathRecord.case_id == case.id)
        .first()
    )

    # Second identifier: the surname, full name or ID number read from
    # the body's own tag. It must match too, or the release stops.
    if not deceased_identifier_matches(
        data.confirm_deceased_identifier, case, death_record
    ):
        audit_remains(
            db,
            remains=remains,
            case=case,
            current_user=current_user,
            action="remains.release_refused",
            notes=(
                "Release was refused: the second identifier did not "
                "match."
            ),
            extra={"reason": "identifier_mismatch"},
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "The surname or ID number does not match these "
                "remains. Check the tag on the body and the case."
            ),
        )

    released_at = check_time(
        data.released_at,
        earliest=remains.received_at,
        label="The release time",
    )

    items = (
        db.query(CasePaperworkItem)
        .filter(CasePaperworkItem.case_id == case.id)
        .all()
    )

    blockers = release_blockers(
        remains=remains,
        death_record=death_record,
        paperwork_items=items,
    )

    override_used = False

    if blockers:
        if not data.override_reason:
            audit_remains(
                db,
                remains=remains,
                case=case,
                current_user=current_user,
                action="remains.release_refused",
                notes="Release was refused: requirements not met.",
                extra={"reason": "requirements", "blockers": blockers},
            )
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot release yet: "
                    + "; ".join(blockers)
                    + ". A manager can override with a reason."
                ),
            )

        allowed = has_permission(
            db,
            user_id=user_id,
            role=current_user["role"],
            permission_key="remains.release_override",
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission required: remains.release_override",
            )

        override_used = True

    previous = remains.current_location_id

    remains.status = "released"
    remains.released_at = released_at
    remains.released_by = user_id
    remains.released_to_name = data.released_to_name
    remains.released_to_id_number = data.released_to_id_number
    remains.released_to_relationship = data.released_to_relationship
    remains.release_override_reason = (
        data.override_reason if override_used else None
    )
    remains.current_location_id = None

    log_event(
        db,
        remains=remains,
        event_type="released",
        occurred_at=released_at,
        performed_by=user_id,
        from_location_id=previous,
        notes=(
            f"Released with override: {data.override_reason}"
            if override_used
            else None
        ),
    )

    audit_remains(
        db,
        remains=remains,
        case=case,
        current_user=current_user,
        action="remains.released",
        notes="Remains were released.",
        extra={
            "from_location_id": str(previous) if previous else None,
            "override_used": override_used,
            "blockers_overridden": blockers if override_used else [],
        },
    )

    tell_operations(
        db,
        business_id=business_id,
        title=f"{case.deceased_full_name} was released from the mortuary",
        body=(
            f"Released to {remains.released_to_name}"
            if remains.released_to_name
            else None
        ),
        link=f"/cases/{case.id}",
        actor_id=user_id,
    )

    db.commit()
    db.refresh(remains)

    return build_detail(db, remains)

# ============================================================
# MORTUARY BELONGINGS REGISTER API
# ============================================================


def get_belonging(
    db: Session,
    *,
    belonging_id: UUID,
    remains: RemainsRecord,
    business_id: UUID,
    lock: bool = False,
) -> MortuaryBelonging:
    query = db.query(MortuaryBelonging).filter(
        MortuaryBelonging.id == belonging_id,
        MortuaryBelonging.remains_id == remains.id,
        MortuaryBelonging.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    item = query.first()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Belonging not found",
        )

    return item


def audit_belonging(
    db: Session,
    *,
    item: MortuaryBelonging,
    case: FuneralCase,
    current_user: dict,
    action: str,
    details: dict | None = None,
) -> None:
    create_audit_log(
        db,
        business_id=item.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="mortuary_belonging",
        entity_id=item.id,
        details={
            "case_id": str(case.id),
            "quantity": item.quantity,
            **(details or {}),
        },
        notes="A mortuary belongings register action was recorded.",
    )


@router.get(
    "/{case_id}/remains/belongings",
    response_model=list[MortuaryBelongingResponse],
)
def list_remains_belongings(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.view")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id)
    remains = get_remains(db, case.id, business_id)

    return (
        db.query(MortuaryBelonging)
        .filter(
            MortuaryBelonging.business_id == business_id,
            MortuaryBelonging.remains_id == remains.id,
        )
        .order_by(
            MortuaryBelonging.received_at,
            MortuaryBelonging.created_at,
        )
        .all()
    )


@router.post(
    "/{case_id}/remains/belongings",
    response_model=MortuaryBelongingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_remains_belonging(
    case_id: UUID,
    data: MortuaryBelongingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_open_remains(db, case.id, business_id)

    item = MortuaryBelonging(
        business_id=business_id,
        remains_id=remains.id,
        description=data.description,
        quantity=data.quantity,
        condition=data.condition,
        storage_location=data.storage_location,
        received_from=data.received_from,
        received_by=get_user_id(current_user),
        received_by_name=data.received_by_name,
        notes=data.notes,
    )

    db.add(item)
    db.flush()

    audit_belonging(
        db,
        item=item,
        case=case,
        current_user=current_user,
        action="mortuary.belonging.created",
        details={"status": "in_safekeeping"},
    )

    db.commit()
    db.refresh(item)

    return item


@router.patch(
    "/{case_id}/remains/belongings/{belonging_id}",
    response_model=MortuaryBelongingResponse,
)
def update_remains_belonging(
    case_id: UUID,
    belonging_id: UUID,
    data: MortuaryBelongingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_open_remains(db, case.id, business_id)

    item = get_belonging(
        db,
        belonging_id=belonging_id,
        remains=remains,
        business_id=business_id,
        lock=True,
    )

    if item.status != "in_safekeeping":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only belongings in safekeeping can be edited",
        )

    updates = data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide at least one field to update",
        )

    changed_fields = []

    for field, value in updates.items():
        if getattr(item, field) != value:
            setattr(item, field, value)
            changed_fields.append(field)

    if changed_fields:
        details = {"changed_fields": sorted(changed_fields)}

        if "quantity" in changed_fields:
            details["quantity"] = item.quantity

        audit_belonging(
            db,
            item=item,
            case=case,
            current_user=current_user,
            action="mortuary.belonging.updated",
            details=details,
        )

    db.commit()
    db.refresh(item)

    return item


@router.post(
    "/{case_id}/remains/belongings/{belonging_id}/return",
    response_model=MortuaryBelongingResponse,
)
def return_remains_belonging(
    case_id: UUID,
    belonging_id: UUID,
    data: MortuaryBelongingReturn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_remains(db, case.id, business_id, lock=True)

    item = get_belonging(
        db,
        belonging_id=belonging_id,
        remains=remains,
        business_id=business_id,
        lock=True,
    )

    if item.status != "in_safekeeping":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only belongings in safekeeping can be returned",
        )

    item.status = "returned"
    item.returned_to_name = data.returned_to_name
    item.returned_by = get_user_id(current_user)
    item.returned_at = datetime.now(timezone.utc)

    if data.notes:
        item.notes = (
            f"{item.notes}\nReturn note: {data.notes}"
            if item.notes
            else f"Return note: {data.notes}"
        )

    audit_belonging(
        db,
        item=item,
        case=case,
        current_user=current_user,
        action="mortuary.belonging.returned",
        details={"status": "returned"},
    )

    db.commit()
    db.refresh(item)

    return item


@router.post(
    "/{case_id}/remains/belongings/{belonging_id}/transfer",
    response_model=MortuaryBelongingResponse,
)
def transfer_remains_belonging(
    case_id: UUID,
    belonging_id: UUID,
    data: MortuaryBelongingTransfer,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("remains.manage")),
):
    business_id = get_business_id(current_user)
    case = get_case(db, case_id, business_id, for_change=True)
    remains = get_open_remains(db, case.id, business_id)

    item = get_belonging(
        db,
        belonging_id=belonging_id,
        remains=remains,
        business_id=business_id,
        lock=True,
    )

    if item.status != "in_safekeeping":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only belongings in safekeeping can be transferred",
        )

    item.status = "transferred"
    item.transferred_to_location = data.transferred_to_location
    item.transferred_by = get_user_id(current_user)
    item.transferred_at = datetime.now(timezone.utc)
    item.storage_location = data.transferred_to_location

    if data.notes:
        item.notes = (
            f"{item.notes}\nTransfer note: {data.notes}"
            if item.notes
            else f"Transfer note: {data.notes}"
        )

    audit_belonging(
        db,
        item=item,
        case=case,
        current_user=current_user,
        action="mortuary.belonging.transferred",
        details={"status": "transferred"},
    )

    db.commit()
    db.refresh(item)

    return item
