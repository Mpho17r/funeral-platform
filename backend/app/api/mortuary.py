from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase
from app.models.branch import Branch
from app.models.mortuary import (
    MortuaryLocation,
    MortuaryLocationBranch,
    RemainsRecord,
)
from app.schemas.mortuary import (
    BoardResponse,
    LocationCreate,
    LocationResponse,
    LocationUpdate,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.branch_service import BranchError, resolve_branch_id
from app.services.mortuary import cooling_status, now_utc, occupancy


router = APIRouter(
    prefix="/mortuary",
    tags=["Mortuary"],
)


AUDITED_LOCATION_FIELDS = ("name", "kind", "capacity", "notes")


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


def get_location_or_404(
    db: Session,
    location_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> MortuaryLocation:
    query = db.query(MortuaryLocation).filter(
        MortuaryLocation.id == location_id,
        MortuaryLocation.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    location = query.first()

    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mortuary location not found",
        )

    return location


def with_occupancy(db: Session, location: MortuaryLocation):
    location.occupied = occupancy(db, location.id)
    location.shared_with = [
        row.branch_id
        for row in db.query(MortuaryLocationBranch)
        .filter(MortuaryLocationBranch.location_id == location.id)
        .all()
    ]

    return location


def audit_location(
    db: Session,
    *,
    location: MortuaryLocation,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    create_audit_log(
        db,
        business_id=location.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="mortuary_location",
        entity_id=location.id,
        details={
            "name": location.name,
            "kind": location.kind,
            **(extra or {}),
        },
        notes=notes,
    )


def duplicate_name_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A mortuary location with that name already exists",
    )


# ============================================================
# LOCATIONS
# ============================================================

@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.manage")),
):
    business_id = get_business_id(current_user)

    try:
        branch_id = resolve_branch_id(
            db,
            business_id=business_id,
            requested=data.branch_id,
            acting_user_id=get_user_id(current_user),
        )
    except BranchError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    location = MortuaryLocation(
        business_id=business_id,
        branch_id=branch_id,
        name=data.name,
        kind=data.kind,
        capacity=data.capacity,
        notes=data.notes,
    )

    db.add(location)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise duplicate_name_error()

    audit_location(
        db,
        location=location,
        current_user=current_user,
        action="mortuary_location.created",
        notes="Mortuary location was created.",
        extra={"capacity": location.capacity},
    )

    db.commit()
    db.refresh(location)

    return with_occupancy(db, location)


@router.get(
    "/locations",
    response_model=list[LocationResponse],
)
def list_locations(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(MortuaryLocation).filter(
        MortuaryLocation.business_id == business_id
    )

    if not include_inactive:
        query = query.filter(MortuaryLocation.is_active.is_(True))

    locations = query.order_by(MortuaryLocation.name).all()

    return [with_occupancy(db, location) for location in locations]


@router.patch(
    "/locations/{location_id}",
    response_model=LocationResponse,
)
def update_location(
    location_id: UUID,
    data: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.manage")),
):
    business_id = get_business_id(current_user)
    location = get_location_or_404(
        db, location_id, business_id, lock=True
    )

    updates = data.model_dump(exclude_unset=True)

    for required in ("name", "kind"):
        if required in updates and updates[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{required} cannot be null",
            )

    new_capacity = updates.get("capacity", location.capacity)
    taken = occupancy(db, location.id)

    if new_capacity is not None and new_capacity < taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{taken} remains are in {location.name}, so it "
                f"cannot hold fewer than {taken}"
            ),
        )

    old_values = snapshot_fields(location, AUDITED_LOCATION_FIELDS)

    for field, value in updates.items():
        setattr(location, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(location, AUDITED_LOCATION_FIELDS),
    )

    if changes:
        audit_location(
            db,
            location=location,
            current_user=current_user,
            action="mortuary_location.updated",
            notes="Mortuary location was updated.",
            extra={"changes": changes},
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise duplicate_name_error()

    db.refresh(location)

    return with_occupancy(db, location)


@router.post(
    "/locations/{location_id}/branches/{branch_id}",
    response_model=LocationResponse,
)
def share_location(
    location_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    """Let another branch use this mortuary location."""
    business_id = get_business_id(current_user)
    location = get_location_or_404(db, location_id, business_id)

    branch = (
        db.query(Branch)
        .filter(Branch.id == branch_id, Branch.business_id == business_id)
        .first()
    )
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=404, detail="Branch not found")
    if branch.id == location.branch_id:
        raise HTTPException(
            status_code=409,
            detail="That branch already hosts this location",
        )

    exists = (
        db.query(MortuaryLocationBranch)
        .filter(
            MortuaryLocationBranch.location_id == location.id,
            MortuaryLocationBranch.branch_id == branch.id,
        )
        .first()
    )
    if exists is None:
        db.add(
            MortuaryLocationBranch(
                business_id=business_id,
                location_id=location.id,
                branch_id=branch.id,
            )
        )
        audit_location(
            db,
            location=location,
            current_user=current_user,
            action="mortuary_location.shared",
            notes=f"Shared with branch {branch.name}.",
            extra={"branch_id": str(branch.id)},
        )
        db.commit()

    return with_occupancy(db, location)


@router.delete(
    "/locations/{location_id}/branches/{branch_id}",
    response_model=LocationResponse,
)
def unshare_location(
    location_id: UUID,
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    """Stop a branch using this location. Refused while that branch's
    own cases are still kept in it."""
    business_id = get_business_id(current_user)
    location = get_location_or_404(db, location_id, business_id)

    link = (
        db.query(MortuaryLocationBranch)
        .filter(
            MortuaryLocationBranch.location_id == location.id,
            MortuaryLocationBranch.branch_id == branch_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Not shared with that branch")

    in_use = (
        db.query(RemainsRecord.id)
        .join(FuneralCase, FuneralCase.id == RemainsRecord.case_id)
        .filter(
            RemainsRecord.current_location_id == location.id,
            FuneralCase.branch_id == branch_id,
        )
        .count()
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{in_use} remains from that branch are still in "
                f"{location.name}. Move them first."
            ),
        )

    db.delete(link)
    audit_location(
        db,
        location=location,
        current_user=current_user,
        action="mortuary_location.unshared",
        notes="Sharing with a branch was removed.",
        extra={"branch_id": str(branch_id)},
    )
    db.commit()

    return with_occupancy(db, location)


@router.post(
    "/locations/{location_id}/deactivate",
    response_model=LocationResponse,
)
def deactivate_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.manage")),
):
    business_id = get_business_id(current_user)
    location = get_location_or_404(
        db, location_id, business_id, lock=True
    )

    if not location.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Location is already inactive",
        )

    taken = occupancy(db, location.id)

    if taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{taken} remains are still in {location.name}. "
                "Move them first."
            ),
        )

    location.is_active = False

    audit_location(
        db,
        location=location,
        current_user=current_user,
        action="mortuary_location.deactivated",
        notes="Mortuary location was deactivated.",
    )

    db.commit()
    db.refresh(location)

    return with_occupancy(db, location)


@router.post(
    "/locations/{location_id}/reactivate",
    response_model=LocationResponse,
)
def reactivate_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.manage")),
):
    business_id = get_business_id(current_user)
    location = get_location_or_404(
        db, location_id, business_id, lock=True
    )

    if location.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Location is already active",
        )

    location.is_active = True

    audit_location(
        db,
        location=location,
        current_user=current_user,
        action="mortuary_location.reactivated",
        notes="Mortuary location was reactivated.",
    )

    db.commit()
    db.refresh(location)

    return with_occupancy(db, location)


# ============================================================
# BOARD: who is where right now
# ============================================================

@router.get(
    "/board",
    response_model=BoardResponse,
)
def mortuary_board(
    branch_id: UUID | None = None,
    location_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.view")),
):
    business_id = get_business_id(current_user)

    query = (
        db.query(RemainsRecord, FuneralCase, MortuaryLocation)
        .join(FuneralCase, FuneralCase.id == RemainsRecord.case_id)
        .outerjoin(
            MortuaryLocation,
            MortuaryLocation.id == RemainsRecord.current_location_id,
        )
        .filter(
            RemainsRecord.business_id == business_id,
            RemainsRecord.status == "in_custody",
        )
    )

    if branch_id is not None:
        query = query.filter(FuneralCase.branch_id == branch_id)

    if location_id is not None:
        query = query.filter(
            RemainsRecord.current_location_id == location_id
        )

    now = now_utc()
    entries = []

    for remains, case, location in query.all():
        cooling = cooling_status(remains, now=now)

        entries.append(
            {
                "remains_id": remains.id,
                "case_id": case.id,
                "case_number": case.case_number,
                "deceased_full_name": case.deceased_full_name,
                "tag_number": remains.tag_number,
                "location_id": remains.current_location_id,
                "location_name": location.name if location else None,
                "received_at": remains.received_at,
                "identified": remains.identified_at is not None,
                **cooling,
            }
        )

    # Remains that should already be cold come first, then the ones
    # that have waited longest.
    entries.sort(
        key=lambda entry: (
            not entry["cooling_overdue"],
            entry["received_at"],
        )
    )

    locations = (
        db.query(MortuaryLocation)
        .filter(
            MortuaryLocation.business_id == business_id,
            MortuaryLocation.is_active.is_(True),
        )
        .order_by(MortuaryLocation.name)
        .all()
    )

    return {
        "in_custody": len(entries),
        "cooling_overdue": sum(
            1 for entry in entries if entry["cooling_overdue"]
        ),
        "entries": entries,
        "locations": [
            with_occupancy(db, location) for location in locations
        ],
    }
