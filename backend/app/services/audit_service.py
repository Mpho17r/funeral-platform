from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


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
