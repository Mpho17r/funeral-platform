from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


# Values that may contain personal or otherwise sensitive information.
# The audit trail records that these fields changed without copying
# their values into the audit history.
SENSITIVE_AUDIT_FIELDS = {
    "deceased_full_name",
    "date_of_birth",
    "date_of_death",
    "next_of_kin_name",
    "next_of_kin_phone",
    "first_name",
    "last_name",
    "phone",
    "email",
    "address",
    "notes",
}


def _serialize_audit_value(value):
    """
    Convert common application values into JSON-safe audit values.
    """
    from datetime import date, datetime
    from decimal import Decimal

    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return str(value)

    return value


def build_audit_changes(
    old_values: dict,
    new_values: dict,
) -> dict:
    """
    Build a compact audit change set.

    Sensitive fields are redacted while still recording that the
    field changed.
    """
    changes = {}

    for field in old_values:
        old_value = old_values[field]
        new_value = new_values[field]

        if old_value == new_value:
            continue

        if field in SENSITIVE_AUDIT_FIELDS:
            changes[field] = {
                "changed": True,
                "old": "[redacted]",
                "new": "[redacted]",
            }
        else:
            changes[field] = {
                "old": _serialize_audit_value(old_value),
                "new": _serialize_audit_value(new_value),
            }

    return changes


def create_audit_log(
    db: Session,
    *,
    business_id: UUID,
    user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    details: dict | None = None,
    notes: str | None = None,
) -> AuditLog:
    """
    Create a tenant-scoped audit log entry.

    The caller is responsible for committing the transaction.
    """

    audit_log = AuditLog(
        business_id=business_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        notes=notes,
    )

    db.add(audit_log)

    return audit_log
