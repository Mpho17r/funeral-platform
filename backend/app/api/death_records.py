from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.case_document import CaseDocument
from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.schemas.death_record import (
    DeathRecordCreate,
    DeathRecordResponse,
    DeathRecordUpdate,
    PaperworkItemCreate,
    PaperworkItemResponse,
    PaperworkItemUpdate,
    PaperworkResponse,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.identity import validate_sa_id
from app.services.paperwork import (
    PaperworkError,
    paperwork_summary,
    standard_items,
    validate_item_update,
)


router = APIRouter(
    prefix="/cases",
    tags=["Death Records"],
)


AUDITED_RECORD_FIELDS = (
    "deceased_id_type",
    "deceased_id_number",
    "time_of_death",
    "place_of_death_type",
    "place_of_death",
    "manner_of_death",
    "unnatural_cause",
    "cause_of_death",
    "certifier_name",
    "forensic_status",
    "police_case_number",
    "infectious_remains",
    "disposal_method",
    "informant_name",
    "informant_relationship",
    "informant_phone",
    "informant_id_number",
    "notes",
)

AUDITED_ITEM_FIELDS = (
    "label",
    "required",
    "status",
    "reference_number",
    "obtained_on",
    "document_id",
    "notes",
)

# Values that can never be null on a record.
NOT_NULL_RECORD_FIELDS = (
    "deceased_id_type",
    "manner_of_death",
    "forensic_status",
    "infectious_remains",
    "disposal_method",
)


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


def get_record(db: Session, case_id: UUID, business_id: UUID):
    return (
        db.query(DeathRecord)
        .filter(
            DeathRecord.case_id == case_id,
            DeathRecord.business_id == business_id,
        )
        .first()
    )


def check_record_rules(values: dict) -> None:
    """Rules across fields, on the values the record will hold."""

    if values["deceased_id_type"] == "sa_id":
        problem = validate_sa_id(values["deceased_id_number"])

        if problem:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=problem,
            )

    informant_id = values.get("informant_id_number")

    if informant_id and informant_id.isdigit() and len(informant_id) == 13:
        problem = validate_sa_id(informant_id)

        if problem:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Informant: {problem}",
            )

    if (
        values.get("unnatural_cause") is not None
        and values["manner_of_death"] != "unnatural"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "An unnatural cause can only be set when the manner "
                "of death is unnatural."
            ),
        )

    if (
        values["manner_of_death"] == "natural"
        and values["forensic_status"] != "not_applicable"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "A natural death cannot have a forensic status. "
                "Change the manner of death first."
            ),
        )


def audit_record(
    db: Session,
    *,
    record: DeathRecord,
    case: FuneralCase,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    create_audit_log(
        db,
        business_id=record.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="death_record",
        entity_id=record.id,
        details={
            "case_id": str(case.id),
            "case_number": case.case_number,
            **(extra or {}),
        },
        notes=notes,
    )


def ordered_items(db: Session, case_id: UUID, business_id: UUID):
    return (
        db.query(CasePaperworkItem)
        .filter(
            CasePaperworkItem.case_id == case_id,
            CasePaperworkItem.business_id == business_id,
        )
        .order_by(
            CasePaperworkItem.sort_order,
            CasePaperworkItem.created_at,
        )
        .all()
    )


def paperwork_payload(db: Session, case_id: UUID, business_id: UUID):
    items = ordered_items(db, case_id, business_id)

    return {
        "items": items,
        "summary": paperwork_summary(items),
    }


# ============================================================
# DEATH RECORD
# ============================================================

@router.post(
    "/{case_id}/death-record",
    response_model=DeathRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_death_record(
    case_id: UUID,
    data: DeathRecordCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("death_records.manage")
    ),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    if get_record(db, case_id, business_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has a death record",
        )

    values = data.model_dump()
    check_record_rules(values)

    record = DeathRecord(
        business_id=business_id,
        case_id=case_id,
        created_by=get_user_id(current_user),
        **values,
    )
    db.add(record)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This case already has a death record",
        )

    audit_record(
        db,
        record=record,
        case=case,
        current_user=current_user,
        action="death_record.created",
        notes="Death record was created.",
        extra={
            "manner_of_death": record.manner_of_death,
            "disposal_method": record.disposal_method,
        },
    )

    db.commit()
    db.refresh(record)

    return record


@router.get(
    "/{case_id}/death-record",
    response_model=DeathRecordResponse,
)
def read_death_record(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("death_records.view")
    ),
):
    business_id = get_business_id(current_user)
    get_case(db, case_id, business_id)

    record = get_record(db, case_id, business_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No death record has been captured for this case",
        )

    return record


@router.patch(
    "/{case_id}/death-record",
    response_model=DeathRecordResponse,
)
def update_death_record(
    case_id: UUID,
    data: DeathRecordUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("death_records.manage")
    ),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    record = (
        db.query(DeathRecord)
        .filter(
            DeathRecord.case_id == case_id,
            DeathRecord.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No death record has been captured for this case",
        )

    updates = data.model_dump(exclude_unset=True)

    for field in NOT_NULL_RECORD_FIELDS:
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )

    # Moving away from an unnatural death clears its cause rather than
    # leaving a stale one behind.
    if (
        "manner_of_death" in updates
        and updates["manner_of_death"] != "unnatural"
        and "unnatural_cause" not in updates
    ):
        updates["unnatural_cause"] = None

    old_values = snapshot_fields(record, AUDITED_RECORD_FIELDS)
    merged = {**old_values, **updates}

    check_record_rules(merged)

    for field, value in updates.items():
        setattr(record, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(record, AUDITED_RECORD_FIELDS),
    )

    if changes:
        audit_record(
            db,
            record=record,
            case=case,
            current_user=current_user,
            action="death_record.updated",
            notes="Death record was updated.",
            extra={"changes": changes},
        )

    db.commit()
    db.refresh(record)

    return record


# ============================================================
# PAPERWORK CHECKLIST
# ============================================================

@router.get(
    "/{case_id}/paperwork",
    response_model=PaperworkResponse,
)
def read_paperwork(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("paperwork.view")),
):
    business_id = get_business_id(current_user)
    get_case(db, case_id, business_id)

    return paperwork_payload(db, case_id, business_id)


@router.post(
    "/{case_id}/paperwork/standard",
    response_model=PaperworkResponse,
)
def add_standard_paperwork(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("paperwork.manage")
    ),
):
    """Add the standard checklist items this case is missing.

    Safe to call again after the manner of death or the way the person
    will be laid to rest changes: it only adds, never removes or
    resets an item that is already there.
    """

    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    record = get_record(db, case_id, business_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Capture the death record first, so the checklist "
                "fits this case"
            ),
        )

    existing = ordered_items(db, case_id, business_id)
    have = {item.item_type for item in existing}
    next_order = max((item.sort_order for item in existing), default=0)

    added = []

    for standard in standard_items(
        manner_of_death=record.manner_of_death,
        disposal_method=record.disposal_method,
        infectious_remains=record.infectious_remains,
    ):
        if standard.item_type in have:
            continue

        next_order += 10

        db.add(
            CasePaperworkItem(
                business_id=business_id,
                case_id=case_id,
                item_type=standard.item_type,
                label=standard.label,
                required=standard.required,
                sort_order=next_order,
            )
        )
        added.append(standard.item_type)

    if added:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=get_user_id(current_user),
            action="paperwork.standard_added",
            entity_type="case",
            entity_id=case_id,
            details={
                "case_number": case.case_number,
                "added": added,
            },
            notes="Standard paperwork was added to the case.",
        )

    try:
        db.commit()
    except IntegrityError:
        # A second request added the same items first.
        db.rollback()

    return paperwork_payload(db, case_id, business_id)


@router.post(
    "/{case_id}/paperwork",
    response_model=PaperworkItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_custom_paperwork(
    case_id: UUID,
    data: PaperworkItemCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("paperwork.manage")
    ),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    last_order = max(
        (
            item.sort_order
            for item in ordered_items(db, case_id, business_id)
        ),
        default=0,
    )

    item = CasePaperworkItem(
        business_id=business_id,
        case_id=case_id,
        item_type="custom",
        label=data.label,
        required=data.required,
        sort_order=last_order + 10,
        notes=data.notes,
    )
    db.add(item)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=get_user_id(current_user),
        action="paperwork.item_added",
        entity_type="paperwork_item",
        entity_id=item.id,
        details={
            "case_id": str(case.id),
            "case_number": case.case_number,
            "label": item.label,
            "required": item.required,
        },
        notes="Custom paperwork item was added.",
    )

    db.commit()
    db.refresh(item)

    return item


@router.patch(
    "/{case_id}/paperwork/{item_id}",
    response_model=PaperworkItemResponse,
)
def update_paperwork_item(
    case_id: UUID,
    item_id: UUID,
    data: PaperworkItemUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("paperwork.manage")
    ),
):
    business_id = get_business_id(current_user)
    case = get_open_case(db, case_id, business_id)

    item = (
        db.query(CasePaperworkItem)
        .filter(
            CasePaperworkItem.id == item_id,
            CasePaperworkItem.case_id == case_id,
            CasePaperworkItem.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paperwork item not found",
        )

    updates = data.model_dump(exclude_unset=True)

    for field in ("status", "label", "required"):
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )

    if item.item_type != "custom":
        for field in ("label", "required"):
            if field in updates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"{field} can only be changed on a custom "
                        "item"
                    ),
                )

    if updates.get("document_id") is not None:
        document = (
            db.query(CaseDocument.id)
            .filter(
                CaseDocument.id == updates["document_id"],
                CaseDocument.case_id == case_id,
                CaseDocument.business_id == business_id,
            )
            .first()
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="That document does not belong to this case",
            )

    old_values = snapshot_fields(item, AUDITED_ITEM_FIELDS)
    merged = {**old_values, **updates}

    try:
        validate_item_update(
            required=merged["required"],
            new_status=merged["status"],
            notes=merged["notes"],
        )
    except PaperworkError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    for field, value in updates.items():
        setattr(item, field, value)

    # Who obtained it, and when, follows the status.
    if "status" in updates:
        if item.status == "obtained":
            item.obtained_by = get_user_id(current_user)

            if item.obtained_on is None:
                item.obtained_on = date.today()
        elif item.status == "pending":
            item.obtained_on = None
            item.obtained_by = None

    changes = build_audit_changes(
        old_values,
        snapshot_fields(item, AUDITED_ITEM_FIELDS),
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=get_user_id(current_user),
            action="paperwork.item_updated",
            entity_type="paperwork_item",
            entity_id=item.id,
            details={
                "case_id": str(case.id),
                "case_number": case.case_number,
                "item_type": item.item_type,
                "changes": changes,
            },
            notes="Paperwork item was updated.",
        )

    db.commit()
    db.refresh(item)

    return item
