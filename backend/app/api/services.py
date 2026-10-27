from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)

from app.models.case_service import CaseService
from app.models.inventory import InventoryItem
from app.services.inventory import InventoryError
from app.services.service_billing import (
    remove_service_from_drafts,
    sync_service_into_drafts,
)
from app.services.stock_automation import sync_service_stock
from app.models.funeral_case import FuneralCase

from app.schemas.case_service import (
    CaseServiceCreate,
    CaseServiceResponse,
    CaseServiceUpdate,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Services"],
)


def _sync_stock(db, service, wanted, current_user, case_number):
    try:
        sync_service_stock(
            db,
            service=service,
            wanted=wanted,
            user_id=UUID(str(current_user["user_id"])),
            case_number=case_number,
        )
    except InventoryError as error:
        db.rollback()
        raise HTTPException(
            status_code=error.status_code, detail=error.detail
        )


# Fields whose changes are recorded in the audit trail.
AUDITED_SERVICE_FIELDS = (
    "service_type",
    "service_name",
    "description",
    "status",
    "quantity",
    "unit_price",
    "total_price",
    "scheduled_date",
    "provider",
    "notes",
)


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User business information is missing",
        )

    try:
        return UUID(str(business_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid business ID",
        )


def get_case(
    db: Session,
    case_id: UUID,
    business_id: UUID,
):
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


def calculate_total_price(
    quantity: int,
    unit_price: Decimal,
) -> Decimal:
    total = Decimal(quantity) * unit_price

    return total.quantize(
        Decimal("0.01")
    )


# ============================================================
# CREATE SERVICE
# POST /cases/{case_id}/services
# ============================================================

@router.post(
    "/{case_id}/services",
    response_model=CaseServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    case_id: UUID,
    service_data: CaseServiceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify case belongs to business
    # --------------------------------------------------------

    case_number = get_case(
        db=db,
        case_id=case_id,
        business_id=business_id,
    ).case_number

    # --------------------------------------------------------
    # Calculate total price
    # --------------------------------------------------------

    total_price = calculate_total_price(
        quantity=service_data.quantity,
        unit_price=service_data.unit_price,
    )

    # --------------------------------------------------------
    # Create service
    # --------------------------------------------------------

    service = CaseService(
        business_id=business_id,
        case_id=case_id,
        service_type=service_data.service_type,
        service_name=service_data.service_name,
        description=service_data.description,
        status=service_data.status,
        quantity=service_data.quantity,
        unit_price=service_data.unit_price,
        total_price=total_price,
        scheduled_date=service_data.scheduled_date,
        provider=service_data.provider,
        notes=service_data.notes,
        inventory_item_id=service_data.inventory_item_id,
    )

    if service.inventory_item_id is not None:
        item = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.id == service.inventory_item_id,
                InventoryItem.business_id == business_id,
            )
            .first()
        )
        if item is None:
            raise HTTPException(422, "Stock item not found")

    db.add(service)
    db.flush()

    if service.inventory_item_id is not None and service.status != "cancelled":
        _sync_stock(db, service, service.quantity, current_user, case_number)

    # Draft quotes and invoices on this case pick the service up.
    sync_service_into_drafts(db, service)

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="case.service_created",
        entity_type="case_service",
        entity_id=service.id,
        details={
            "case_id": str(case_id),
            "service_type": service.service_type,
            "quantity": service.quantity,
            "unit_price": str(service.unit_price),
            "total_price": str(service.total_price),
        },
        notes="Case service was created.",
    )

    db.commit()
    db.refresh(service)

    return service


# ============================================================
# LIST SERVICES
# GET /cases/{case_id}/services
# ============================================================

@router.get(
    "/{case_id}/services",
    response_model=list[CaseServiceResponse],
)
def list_case_services(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify case belongs to business
    # --------------------------------------------------------

    get_case(
        db=db,
        case_id=case_id,
        business_id=business_id,
    )

    # --------------------------------------------------------
    # Get services
    # --------------------------------------------------------

    services = (
        db.query(CaseService)
        .filter(
            CaseService.case_id == case_id,
            CaseService.business_id == business_id,
        )
        .order_by(
            CaseService.created_at.desc()
        )
        .all()
    )

    return services


# ============================================================
# GET SINGLE SERVICE
# GET /cases/services/{service_id}
# ============================================================

@router.get(
    "/services/{service_id}",
    response_model=CaseServiceResponse,
)
def get_service(
    service_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    business_id = get_business_id(current_user)

    service = (
        db.query(CaseService)
        .filter(
            CaseService.id == service_id,
            CaseService.business_id == business_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return service


# ============================================================
# UPDATE SERVICE
# PATCH /cases/services/{service_id}
# ============================================================

@router.patch(
    "/services/{service_id}",
    response_model=CaseServiceResponse,
)
def update_service(
    service_id: UUID,
    service_data: CaseServiceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Find service
    # --------------------------------------------------------

    service = (
        db.query(CaseService)
        .filter(
            CaseService.id == service_id,
            CaseService.business_id == business_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    # --------------------------------------------------------
    # Apply updates
    # --------------------------------------------------------

    updates = service_data.model_dump(
        exclude_unset=True
    )

    old_values = snapshot_fields(
        service,
        AUDITED_SERVICE_FIELDS,
    )

    for field, value in updates.items():
        setattr(service, field, value)

    # --------------------------------------------------------
    # Recalculate total price
    # --------------------------------------------------------

    quantity = service.quantity or 1
    unit_price = service.unit_price or Decimal("0.00")

    service.total_price = calculate_total_price(
        quantity=quantity,
        unit_price=Decimal(str(unit_price)),
    )

    # Keep stock in step: a cancelled line gives its stock back.
    if service.inventory_item_id is not None and (
        "quantity" in updates or "status" in updates
    ):
        case = db.get(FuneralCase, service.case_id)
        _sync_stock(
            db,
            service,
            0 if service.status == "cancelled" else (service.quantity or 1),
            current_user,
            case.case_number if case else None,
        )

    # Keep any draft quote or invoice in step with the new price/quantity.
    db.flush()
    sync_service_into_drafts(db, service)

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    changes = build_audit_changes(
        old_values,
        snapshot_fields(service, AUDITED_SERVICE_FIELDS),
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="case.service_updated",
            entity_type="case_service",
            entity_id=service.id,
            details={
                "case_id": str(service.case_id),
                "changes": changes,
            },
            notes="Case service was updated.",
        )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()
    db.refresh(service)

    return service


# ============================================================
# DELETE SERVICE
# DELETE /cases/services/{service_id}
# ============================================================

@router.delete(
    "/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_service(
    service_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Find service
    # --------------------------------------------------------

    service = (
        db.query(CaseService)
        .filter(
            CaseService.id == service_id,
            CaseService.business_id == business_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    # --------------------------------------------------------
    # Audit, then delete
    # --------------------------------------------------------

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="case.service_deleted",
        entity_type="case_service",
        entity_id=service.id,
        details={
            "case_id": str(service.case_id),
            "service_type": service.service_type,
            "total_price": str(service.total_price),
        },
        notes="Case service was deleted.",
    )

    if service.inventory_item_id is not None and service.stock_issued:
        case = db.get(FuneralCase, service.case_id)
        _sync_stock(
            db, service, 0, current_user, case.case_number if case else None
        )

    remove_service_from_drafts(db, service)

    db.delete(service)
    db.commit()

    return None
