from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.inventory import Supplier
from app.schemas.inventory import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)


router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"],
)


AUDITED_SUPPLIER_FIELDS = (
    "name",
    "contact_person",
    "phone",
    "email",
    "address",
    "notes",
)


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def get_supplier_or_404(
    db: Session,
    supplier_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> Supplier:
    query = db.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    supplier = query.first()

    if supplier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    return supplier


def duplicate_name():
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A supplier with that name already exists",
    )


def audit_supplier(
    db: Session,
    *,
    supplier: Supplier,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    details = {"name": supplier.name}

    if extra:
        details.update(extra)

    create_audit_log(
        db,
        business_id=supplier.business_id,
        user_id=UUID(str(current_user["user_id"])),
        action=action,
        entity_type="supplier",
        entity_id=supplier.id,
        details=details,
        notes=notes,
    )


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("suppliers.manage")),
):
    business_id = get_business_id(current_user)

    supplier = Supplier(
        business_id=business_id,
        **data.model_dump(),
        is_active=True,
    )

    db.add(supplier)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise duplicate_name()

    audit_supplier(
        db,
        supplier=supplier,
        current_user=current_user,
        action="supplier.created",
        notes="Supplier was created.",
    )

    db.commit()
    db.refresh(supplier)

    return supplier


@router.get(
    "",
    response_model=list[SupplierResponse],
)
def list_suppliers(
    include_inactive: bool = False,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("suppliers.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(Supplier).filter(
        Supplier.business_id == business_id
    )

    if not include_inactive:
        query = query.filter(Supplier.is_active.is_(True))

    if search and search.strip():
        like = f"%{search.strip()}%"

        query = query.filter(
            Supplier.name.ilike(like)
            | Supplier.contact_person.ilike(like)
        )

    return query.order_by(Supplier.name).all()


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
)
def get_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("suppliers.view")),
):
    return get_supplier_or_404(
        db, supplier_id, get_business_id(current_user)
    )


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
)
def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("suppliers.manage")),
):
    business_id = get_business_id(current_user)

    supplier = get_supplier_or_404(
        db, supplier_id, business_id, lock=True
    )

    updates = data.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="name cannot be null",
        )

    old_values = snapshot_fields(supplier, AUDITED_SUPPLIER_FIELDS)

    for field, value in updates.items():
        setattr(supplier, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(supplier, AUDITED_SUPPLIER_FIELDS),
    )

    if changes:
        audit_supplier(
            db,
            supplier=supplier,
            current_user=current_user,
            action="supplier.updated",
            notes="Supplier was updated.",
            extra={"changes": changes},
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise duplicate_name()

    db.refresh(supplier)

    return supplier


@router.post(
    "/{supplier_id}/deactivate",
    response_model=SupplierResponse,
)
def deactivate_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("suppliers.manage")),
):
    supplier = get_supplier_or_404(
        db, supplier_id, get_business_id(current_user), lock=True
    )

    if not supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier is already inactive",
        )

    supplier.is_active = False

    audit_supplier(
        db,
        supplier=supplier,
        current_user=current_user,
        action="supplier.deactivated",
        notes="Supplier was deactivated.",
    )

    db.commit()
    db.refresh(supplier)

    return supplier


@router.post(
    "/{supplier_id}/reactivate",
    response_model=SupplierResponse,
)
def reactivate_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("suppliers.manage")),
):
    supplier = get_supplier_or_404(
        db, supplier_id, get_business_id(current_user), lock=True
    )

    if supplier.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier is already active",
        )

    supplier.is_active = True

    audit_supplier(
        db,
        supplier=supplier,
        current_user=current_user,
        action="supplier.reactivated",
        notes="Supplier was reactivated.",
    )

    db.commit()
    db.refresh(supplier)

    return supplier
