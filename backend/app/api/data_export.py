import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.business import Business
from app.services import backup_status, scheduler_state
from app.services.audit_service import create_audit_log
from app.services.data_export import build_export

router = APIRouter(prefix="/data-export", tags=["Data export"])


@router.post("")
def download_export(
    include_files: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("data.export")),
):
    """Everything this business holds, as a ZIP of CSV files."""
    business_id = UUID(str(current_user["business_id"]))
    user_id = UUID(str(current_user["user_id"]))
    business = db.get(Business, business_id)

    archive, counts, file_count = build_export(
        db,
        business_id=business_id,
        business_name=business.name if business else "",
        exported_by=str(user_id),
        include_files=include_files,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="data.exported",
        entity_type="business",
        entity_id=business_id,
        details={
            "tables": len(counts),
            "rows": sum(counts.values()),
            "files": file_count,
            "include_files": include_files,
        },
        notes="A full export of the business's data was downloaded.",
    )
    db.commit()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def stream():
        try:
            while chunk := archive.read(1024 * 256):
                yield chunk
        finally:
            archive.close()

    return StreamingResponse(
        stream(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="funeralos-export-{stamp}.zip"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/backup-status")
def get_backup_status(
    current_user: dict = Depends(require_permission("data.export")),
):
    """When the last automatic database backup ran, and whether it is stale."""
    return {**backup_status.read(), "scheduler": scheduler_state.read()}
