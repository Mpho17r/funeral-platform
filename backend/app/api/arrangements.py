from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.arrangement import CaseCollection, FuneralArrangement
from app.models.funeral_case import FuneralCase
from app.schemas.arrangement import (
    ArrangementCreate,
    ArrangementResponse,
    ArrangementTransition,
    ArrangementUpdate,
    CollectionCreate,
    CollectionResponse,
    CollectionTransition,
    CollectionUpdate,
    RunSheetResponse,
)
from app.services.arrangement import (
    ArrangementError,
    build_run_sheet,
    check_arrangement_transition,
    check_can_confirm,
    check_collection_time,
    check_collection_transition,
    check_timeline,
    check_vehicle_and_driver,
    local_date,
    now_utc,
)
from app.services.automatic_case_lifecycle import sync_case_status_from_arrangement
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)


router = APIRouter(
    tags=["Arrangements and Collections"],
)


AUDITED_ARRANGEMENT_FIELDS = (
    "status",
    "wake_at",
    "wake_venue",
    "wake_address",
    "service_at",
    "service_venue_type",
    "service_venue",
    "service_address",
    "officiant",
    "departure_at",
    "departure_point",
    "committal_at",
    "committal_place",
    "committal_section",
    "grave_number",
    "grave_confirmed",
    "notes",
    "cancel_reason",
)

AUDITED_COLLECTION_FIELDS = (
    "status",
    "scheduled_at",
    "pickup_type",
    "pickup_address",
    "pickup_contact_name",
    "pickup_contact_phone",
    "vehicle_resource_id",
    "driver_user_id",
    "collected_at",
    "cancel_reason",
    "notes",
)

NOT_NULL_ARRANGEMENT_FIELDS = ("grave_confirmed",)
NOT_NULL_COLLECTION_FIELDS = ("scheduled_at", "pickup_type")


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


def get_case(db: Session, case_id: UUID, business_id: UUID):
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


def get_open_case(db: Session, case_id: UUID, business_id: UUID):
    """The case, locked, for a change. Archived cases are frozen."""

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    if case.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived cases cannot be changed. Restore it first.",
        )

    return case


def rule_error(error: ArrangementError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


def audit(
    db: Session,
    *,
    entity_type: str,
    entity,
    case: FuneralCase,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    create_audit_log(
        db,
        business_id=entity.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type=entity_type,
        entity_id=entity.id,
        details={
            "case_id": str(case.id),
            "case_number": case.case_number,
            **(extra or {}),
        },
        notes=notes,
    )


# ============================================================
# ARRANGEMENT
# ============================================================

def get_arrangement(
    db: Session, case_id: UUID, business_id: UUID, *, lock: bool = False
):
    query = db.query(FuneralArrangement).filter(
        FuneralArrangement.case_id == case_id,
        FuneralArrangement.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    return query.first()


def sync_case(case: FuneralCase, arrangement: FuneralArrangement) -> dict:
    """Keep the case's funeral date and venue, which the calendar and
    dashboard read, in step with the arrangement. Returns what changed
    so it can be recorded."""

    if arrangement.status == "cancelled":
        date_value = None
        venue = None
    else:
        date_value = (
            local_date(arrangement.committal_at)
            if arrangement.committal_at
            else None
        )
        venue = arrangement.committal_place

    changes = {}

    if case.funeral_date != date_value:
        changes["funeral_date"] = {
            "old": case.funeral_date.isoformat() if case.funeral_date else None,
            "new": date_value.isoformat() if date_value else None,
        }
        case.funeral_date = date_value

    if case.funeral_venue != venue:
        changes["funeral_venue"] = {"changed": True}
        case.funeral_venue = venue

    return changes


def arrangement_values(arrangement: FuneralArrangement) -> dict:
    return {
        field: getattr(arrangement, field)
        for field in (
            "status",
            "wake_at",
            "service_at",
            "departure_at",
            "committal_at",
            "committal_place",
        )
    }


@router.post(
    "/cases/{case_id}/arrangement",
    response_model=ArrangementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_arrangement(
    case_id: UUID,
    data: ArrangementCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("arrangements.manage")),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    if get_arrangement(db, case_id, business_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has funeral arrangements",
        )

    values = data.model_dump()

    try:
        check_timeline(values, date_of_death=case.date_of_death)
    except ArrangementError as error:
        raise rule_error(error)

    arrangement = FuneralArrangement(
        business_id=business_id,
        case_id=case_id,
        created_by=get_user_id(current_user),
        **values,
    )
    db.add(arrangement)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has funeral arrangements",
        )

    case_changes = sync_case(case, arrangement)
    sync_case_status_from_arrangement(
        db,
        case=case,
        arrangement=arrangement,
        user_id=get_user_id(current_user),
    )

    audit(
        db,
        entity_type="funeral_arrangement",
        entity=arrangement,
        case=case,
        current_user=current_user,
        action="arrangement.created",
        notes="Funeral arrangements were created.",
        extra={"case_changes": case_changes} if case_changes else None,
    )

    db.commit()
    db.refresh(arrangement)

    return arrangement


@router.get(
    "/cases/{case_id}/arrangement",
    response_model=ArrangementResponse,
)
def read_arrangement(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("arrangements.view")),
):
    business_id = get_business_id(current_user)
    get_case(db, case_id, business_id)

    arrangement = get_arrangement(db, case_id, business_id)

    if arrangement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No funeral arrangements have been made for this case",
        )

    return arrangement


@router.patch(
    "/cases/{case_id}/arrangement",
    response_model=ArrangementResponse,
)
def update_arrangement(
    case_id: UUID,
    data: ArrangementUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("arrangements.manage")),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    arrangement = get_arrangement(db, case_id, business_id, lock=True)

    if arrangement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No funeral arrangements have been made for this case",
        )

    if arrangement.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A {arrangement.status} arrangement cannot be changed"
                + (
                    ". Reopen it first."
                    if arrangement.status == "cancelled"
                    else ""
                )
            ),
        )

    updates = data.model_dump(exclude_unset=True)

    for field in NOT_NULL_ARRANGEMENT_FIELDS:
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )

    old_values = snapshot_fields(arrangement, AUDITED_ARRANGEMENT_FIELDS)
    merged = {**arrangement_values(arrangement), **updates}

    try:
        check_timeline(merged, date_of_death=case.date_of_death)

        # A confirmed funeral must stay confirmable.
        if arrangement.status == "confirmed":
            check_can_confirm(merged)
    except ArrangementError as error:
        raise rule_error(error)

    for field, value in updates.items():
        setattr(arrangement, field, value)

    case_changes = sync_case(case, arrangement)
    sync_case_status_from_arrangement(
        db,
        case=case,
        arrangement=arrangement,
        user_id=get_user_id(current_user),
    )

    changes = build_audit_changes(
        old_values,
        snapshot_fields(arrangement, AUDITED_ARRANGEMENT_FIELDS),
    )

    if changes:
        audit(
            db,
            entity_type="funeral_arrangement",
            entity=arrangement,
            case=case,
            current_user=current_user,
            action="arrangement.updated",
            notes="Funeral arrangements were updated.",
            extra={
                "changes": changes,
                **({"case_changes": case_changes} if case_changes else {}),
            },
        )

    db.commit()
    db.refresh(arrangement)

    return arrangement


@router.post(
    "/cases/{case_id}/arrangement/transition",
    response_model=ArrangementResponse,
)
def transition_arrangement(
    case_id: UUID,
    data: ArrangementTransition,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("arrangements.manage")),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    arrangement = get_arrangement(db, case_id, business_id, lock=True)

    if arrangement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No funeral arrangements have been made for this case",
        )

    old_status = arrangement.status

    try:
        check_arrangement_transition(
            old_status,
            data.status,
            reason=data.reason,
            values=arrangement_values(arrangement),
        )
    except ArrangementError as error:
        raise rule_error(error)

    now = now_utc()
    arrangement.status = data.status

    if data.status == "confirmed":
        arrangement.confirmed_at = now
        arrangement.confirmed_by = get_user_id(current_user)
    elif data.status == "completed":
        arrangement.completed_at = now
    elif data.status == "cancelled":
        arrangement.cancelled_at = now
        arrangement.cancel_reason = data.reason
    elif data.status == "draft":
        # Reopened or taken back to draft: nothing is confirmed.
        arrangement.confirmed_at = None
        arrangement.confirmed_by = None
        arrangement.cancelled_at = None
        arrangement.cancel_reason = None

    case_changes = sync_case(case, arrangement)
    sync_case_status_from_arrangement(
        db,
        case=case,
        arrangement=arrangement,
        user_id=get_user_id(current_user),
    )

    audit(
        db,
        entity_type="funeral_arrangement",
        entity=arrangement,
        case=case,
        current_user=current_user,
        action=f"arrangement.{data.status}",
        notes=f"Funeral arrangements moved from {old_status} to {data.status}.",
        extra={
            "from": old_status,
            "to": data.status,
            **({"reason_given": True} if data.reason else {}),
            **({"case_changes": case_changes} if case_changes else {}),
        },
    )

    db.commit()
    db.refresh(arrangement)

    return arrangement


# ============================================================
# COLLECTIONS
# ============================================================

def get_collection(
    db: Session,
    case_id: UUID,
    collection_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
):
    query = db.query(CaseCollection).filter(
        CaseCollection.id == collection_id,
        CaseCollection.case_id == case_id,
        CaseCollection.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    collection = query.first()

    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    return collection


@router.post(
    "/cases/{case_id}/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_collection(
    case_id: UUID,
    data: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("collections.manage")),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    values = data.model_dump()

    try:
        check_collection_time(
            values["scheduled_at"], date_of_death=case.date_of_death
        )
        check_vehicle_and_driver(
            db,
            business_id=business_id,
            vehicle_resource_id=values["vehicle_resource_id"],
            driver_user_id=values["driver_user_id"],
        )
    except ArrangementError as error:
        raise rule_error(error)

    collection = CaseCollection(
        business_id=business_id,
        case_id=case_id,
        created_by=get_user_id(current_user),
        **values,
    )
    db.add(collection)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This case already has an open collection. Complete or "
                "cancel it first."
            ),
        )

    audit(
        db,
        entity_type="case_collection",
        entity=collection,
        case=case,
        current_user=current_user,
        action="collection.created",
        notes="A collection was scheduled.",
        extra={"scheduled_at": collection.scheduled_at.isoformat()},
    )

    db.commit()
    db.refresh(collection)

    return collection


@router.get(
    "/cases/{case_id}/collections",
    response_model=list[CollectionResponse],
)
def list_collections(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("collections.view")),
):
    business_id = get_business_id(current_user)
    get_case(db, case_id, business_id)

    return (
        db.query(CaseCollection)
        .filter(
            CaseCollection.case_id == case_id,
            CaseCollection.business_id == business_id,
        )
        .order_by(CaseCollection.scheduled_at.desc())
        .all()
    )


@router.patch(
    "/cases/{case_id}/collections/{collection_id}",
    response_model=CollectionResponse,
)
def update_collection(
    case_id: UUID,
    collection_id: UUID,
    data: CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("collections.manage")),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)
    collection = get_collection(
        db, case_id, collection_id, business_id, lock=True
    )

    if collection.status not in ("scheduled", "en_route"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {collection.status} collection cannot be changed",
        )

    updates = data.model_dump(exclude_unset=True)

    for field in NOT_NULL_COLLECTION_FIELDS:
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )

    # A collection that is out cannot lose its vehicle or driver.
    if collection.status == "en_route":
        for field, label in (
            ("vehicle_resource_id", "vehicle"),
            ("driver_user_id", "driver"),
        ):
            if field in updates and updates[field] is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"The {label} cannot be removed while the "
                        "collection is on its way"
                    ),
                )

    try:
        if updates.get("scheduled_at") is not None:
            check_collection_time(
                updates["scheduled_at"], date_of_death=case.date_of_death
            )

        check_vehicle_and_driver(
            db,
            business_id=business_id,
            vehicle_resource_id=updates.get("vehicle_resource_id"),
            driver_user_id=updates.get("driver_user_id"),
        )
    except ArrangementError as error:
        raise rule_error(error)

    old_values = snapshot_fields(collection, AUDITED_COLLECTION_FIELDS)

    for field, value in updates.items():
        setattr(collection, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(collection, AUDITED_COLLECTION_FIELDS),
    )

    if changes:
        audit(
            db,
            entity_type="case_collection",
            entity=collection,
            case=case,
            current_user=current_user,
            action="collection.updated",
            notes="A collection was updated.",
            extra={"changes": changes},
        )

    db.commit()
    db.refresh(collection)

    return collection


@router.post(
    "/cases/{case_id}/collections/{collection_id}/transition",
    response_model=CollectionResponse,
)
def transition_collection(
    case_id: UUID,
    collection_id: UUID,
    data: CollectionTransition,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("collections.manage")),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)
    collection = get_collection(
        db, case_id, collection_id, business_id, lock=True
    )

    old_status = collection.status

    try:
        collected_at = check_collection_transition(
            collection,
            data.status,
            reason=data.reason,
            collected_at=data.collected_at,
        )
    except ArrangementError as error:
        raise rule_error(error)

    now = now_utc()
    collection.status = data.status

    if data.status == "en_route":
        collection.en_route_at = now
    elif data.status == "scheduled":
        collection.en_route_at = None
    elif data.status == "collected":
        collection.collected_at = collected_at
    elif data.status == "cancelled":
        collection.cancelled_at = now
        collection.cancel_reason = data.reason

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has an open collection",
        )

    audit(
        db,
        entity_type="case_collection",
        entity=collection,
        case=case,
        current_user=current_user,
        action=f"collection.{data.status}",
        notes=f"Collection moved from {old_status} to {data.status}.",
        extra={
            "from": old_status,
            "to": data.status,
            **({"reason_given": True} if data.reason else {}),
        },
    )

    db.commit()
    db.refresh(collection)

    return collection


# ============================================================
# RUN SHEET
# ============================================================

@router.get(
    "/run-sheet",
    response_model=RunSheetResponse,
)
def read_run_sheet(
    day: date | None = Query(default=None, alias="date"),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("run_sheet.view")),
):
    business_id = get_business_id(current_user)

    if day is None:
        day = local_date(now_utc())

    return build_run_sheet(
        db,
        business_id=business_id,
        day=day,
        branch_id=branch_id,
    )
