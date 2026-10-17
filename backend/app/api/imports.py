from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.member import Member
from app.models.membership import Membership
from app.services.audit_service import create_audit_log
from app.services.branch_service import BranchError, resolve_branch_id
from app.services.member_import import (
    ImportFileError,
    RowResult,
    check_rows,
    read_rows,
    template_csv,
)


router = APIRouter(prefix="/imports", tags=["Imports"])

MEMBERSHIP_STATUS_FOR = {
    "active": "active",
    "arrears": "arrears",
    "lapsed": "lapsed",
    "cancelled": "cancelled",
    "deceased": "cancelled",
}


async def _read(upload: UploadFile) -> bytes:
    return await upload.read()


def _results_for(db, current_user, raw: bytes):
    try:
        rows = read_rows(raw)
    except ImportFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    return check_rows(db, UUID(str(current_user["business_id"])), rows)


def _summary(results: list[RowResult], ignored: list[str]) -> dict:
    return {
        "total": len(results),
        "ready": sum(1 for r in results if r.ok),
        "with_errors": sum(1 for r in results if not r.ok),
        "policies": sum(1 for r in results if r.ok and r.membership),
        "ignored_columns": ignored,
        "rows": [
            {
                "line": r.line,
                "member_number": r.values.get("member_number", ""),
                "name": " ".join(
                    p for p in (
                        r.values.get("first_name", ""),
                        r.values.get("last_name", ""),
                    ) if p
                ),
                "plan": r.values.get("plan", ""),
                "ok": r.ok,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            for r in results
        ],
    }


@router.get("/members/template")
def members_template(
    current_user: dict = Depends(require_permission("imports.run")),
):
    return Response(
        content=template_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="members-template.csv"'
        },
    )


@router.post("/members/check")
async def check_members_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("imports.run")),
):
    """Read the file and report what would happen. Saves nothing."""

    results, ignored = _results_for(db, current_user, await _read(file))

    return _summary(results, ignored)


@router.post("/members")
async def import_members_file(
    file: UploadFile = File(...),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("imports.run")),
):
    """Save every row that passed the check. Rows with problems are left
    out and reported, so a file can be fixed and uploaded again."""

    business_id = UUID(str(current_user["business_id"]))
    actor = UUID(str(current_user["user_id"]))

    results, ignored = _results_for(db, current_user, await _read(file))

    try:
        branch = resolve_branch_id(
            db,
            business_id=business_id,
            requested=branch_id,
            acting_user_id=current_user["user_id"],
        )
    except BranchError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    members = 0
    policies = 0

    for row in results:
        if not row.ok or row.payload is None:
            continue

        p = row.payload
        member = Member(
            business_id=business_id,
            branch_id=branch,
            member_number=p.member_number.strip(),
            first_name=p.first_name.strip(),
            last_name=p.last_name.strip(),
            id_number=p.id_number,
            date_of_birth=p.date_of_birth,
            phone=p.phone,
            email=p.email,
            address=p.address,
            join_date=p.join_date or date.today(),
            status=p.status,
        )
        db.add(member)
        db.flush()
        members += 1

        if row.membership and row.plan_id:
            state = MEMBERSHIP_STATUS_FOR.get(p.status, "active")
            due = row.membership["next_due_date"]

            db.add(
                Membership(
                    business_id=business_id,
                    member_id=member.id,
                    plan_id=row.plan_id,
                    membership_number=row.membership["membership_number"],
                    start_date=row.membership["start_date"],
                    status=state,
                    next_due_date=due,
                    arrears_since=due if state == "arrears" else None,
                    lapsed_at=due if state == "lapsed" else None,
                    cancelled_at=(
                        date.today() if state == "cancelled" else None
                    ),
                )
            )
            policies += 1

    skipped = sum(1 for r in results if not r.ok)

    # One entry for the whole import. Personal details stay out of it.
    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor,
        action="import.members",
        entity_type="import",
        entity_id=None,
        details={
            "filename": (file.filename or "")[:200],
            "members_created": members,
            "policies_created": policies,
            "rows_skipped": skipped,
        },
        notes=f"Imported {members} members from a file.",
    )

    db.commit()

    summary = _summary(results, ignored)
    summary.update(
        imported=members,
        policies_created=policies,
        skipped=skipped,
    )

    return summary
