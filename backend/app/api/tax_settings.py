"""Main Admin controls for business VAT registration and pricing convention."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_main_admin
from app.models.business import Business
from app.services.audit_service import create_audit_log, snapshot_fields, build_audit_changes

router = APIRouter(prefix="/businesses", tags=["Business Tax Settings"])

TAX_FIELDS = ("vat_registered", "vat_registration_number", "prices_include_vat")


class BusinessTaxSettingsUpdate(BaseModel):
    vat_registered: bool
    vat_registration_number: str | None = Field(default=None, max_length=50)
    prices_include_vat: bool = False

    @model_validator(mode="after")
    def validate_registration(self):
        self.vat_registration_number = (
            (self.vat_registration_number or "").strip() or None
        )
        if self.vat_registered and not self.vat_registration_number:
            raise ValueError(
                "Enter the VAT registration number when the business is VAT registered."
            )
        if not self.vat_registered:
            self.vat_registration_number = None
        return self


class BusinessTaxSettingsResponse(BaseModel):
    vat_registered: bool
    vat_registration_number: str | None
    prices_include_vat: bool
    standard_vat_rate: str = "15.00"
    currency: str = "ZAR"


def _business_id(current_user: dict) -> UUID:
    value = current_user.get("business_id")
    if not value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )
    return UUID(str(value))


@router.get("/{business_id}/tax-settings", response_model=BusinessTaxSettingsResponse)
def get_tax_settings(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):
    if _business_id(current_user) != business_id:
        raise HTTPException(status_code=403, detail="You do not have access to this business")
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessTaxSettingsResponse(
        vat_registered=business.vat_registered,
        vat_registration_number=business.vat_registration_number,
        prices_include_vat=business.prices_include_vat,
    )


@router.patch("/{business_id}/tax-settings", response_model=BusinessTaxSettingsResponse)
def update_tax_settings(
    business_id: UUID,
    data: BusinessTaxSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):
    if _business_id(current_user) != business_id:
        raise HTTPException(status_code=403, detail="You do not have access to this business")
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    before = snapshot_fields(business, TAX_FIELDS)
    business.vat_registered = data.vat_registered
    business.vat_registration_number = data.vat_registration_number
    business.prices_include_vat = data.prices_include_vat
    changes = build_audit_changes(before, snapshot_fields(business, TAX_FIELDS))
    if changes:
        create_audit_log(
            db,
            business_id=business.id,
            user_id=UUID(str(current_user["user_id"])),
            action="business.tax_settings_updated",
            entity_type="business",
            entity_id=business.id,
            details={"changes": changes},
            notes="Business VAT registration and pricing settings were updated.",
        )
    db.commit()
    db.refresh(business)
    return BusinessTaxSettingsResponse(
        vat_registered=business.vat_registered,
        vat_registration_number=business.vat_registration_number,
        prices_include_vat=business.prices_include_vat,
    )
