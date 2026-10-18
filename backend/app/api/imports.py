from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.services.audit_service import create_audit_log
from app.services.branch_service import BranchError, resolve_branch_id
from app.services.membership_status import recalculate_membership_status
from app.models.funeral_case import FuneralCase
from app.services import case_import, payment_import
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


# ============================================================
# PAYMENT HISTORY
# ============================================================

def _payment_summary(rows, ignored: list[str]) -> dict:
    return {
        "total": len(rows),
        "ready": sum(1 for r in rows if r.ok),
        "with_errors": sum(1 for r in rows if not r.ok),
        "total_amount": str(
            sum((r.amount for r in rows if r.ok and r.amount), Decimal("0.00"))
        ),
        "ignored_columns": ignored,
        "rows": [
            {
                "line": r.line,
                "member_number": r.values.get("membership_number", ""),
                "name": (
                    f"{r.values.get('payment_date', '')} · "
                    f"{r.values.get('amount', '')}"
                ),
                "plan": r.values.get("month", ""),
                "ok": r.ok,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            for r in rows
        ],
    }


def _payment_results(db, current_user, raw: bytes):
    try:
        rows = payment_import.read_rows(raw)
    except ImportFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    return payment_import.check_rows(
        db, UUID(str(current_user["business_id"])), rows
    )


@router.get("/payments/template")
def payments_template(
    current_user: dict = Depends(require_permission("imports.run")),
):
    return Response(
        content=payment_import.template_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="payments-template.csv"'
        },
    )


@router.post("/payments/check")
async def check_payments_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("imports.run")),
):
    """Report what would happen. Saves nothing."""

    rows, ignored = _payment_results(db, current_user, await _read(file))

    return _payment_summary(rows, ignored)


@router.post("/payments")
async def import_payments_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("imports.run")),
):
    """Record every payment that passed the check, apply each to its
    month, then bring each affected policy's status up to date."""

    from app.api.membership_payments import recalculate_contribution

    business_id = UUID(str(current_user["business_id"]))
    actor = UUID(str(current_user["user_id"]))

    rows, ignored = _payment_results(db, current_user, await _read(file))

    good = sorted(
        (r for r in rows if r.ok and r.membership_id and r.amount),
        key=lambda r: (r.paid_on, r.line),
    )

    touched_memberships: set[UUID] = set()
    touched_contributions: dict[UUID, date] = {}
    created_contributions = 0
    total = Decimal("0.00")

    for row in good:
        contribution = None

        if row.period:
            contribution = (
                db.query(MembershipContribution)
                .filter(
                    MembershipContribution.membership_id == row.membership_id,
                    MembershipContribution.contribution_period == row.period,
                )
                .first()
            )

            if contribution is None:
                contribution = MembershipContribution(
                    business_id=business_id,
                    membership_id=row.membership_id,
                    contribution_period=row.period,
                    amount_due=row.plan_amount,
                    amount_paid=Decimal("0.00"),
                    due_date=row.period,
                    status="due",
                )
                db.add(contribution)
                db.flush()
                created_contributions += 1

        db.add(
            MembershipPayment(
                business_id=business_id,
                membership_id=row.membership_id,
                contribution_id=contribution.id if contribution else None,
                amount=row.amount,
                payment_method=row.method,
                reference=row.reference,
                payment_date=row.paid_on,
                notes=row.notes,
            )
        )
        db.flush()

        total += row.amount
        touched_memberships.add(row.membership_id)

        if contribution:
            recalculate_contribution(db, contribution)
            # The month was settled on the day the money came in, not today.
            if contribution.status == "paid":
                contribution.paid_at = row.paid_on

    for membership_id in touched_memberships:
        membership = db.get(Membership, membership_id)
        recalculate_membership_status(db, membership)

    skipped = sum(1 for r in rows if not r.ok)

    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor,
        action="import.payments",
        entity_type="import",
        entity_id=None,
        details={
            "filename": (file.filename or "")[:200],
            "payments_created": len(good),
            "months_created": created_contributions,
            "total_amount": str(total),
            "memberships_updated": len(touched_memberships),
            "rows_skipped": skipped,
        },
        notes=f"Imported {len(good)} payments from a file.",
    )

    db.commit()

    summary = _payment_summary(rows, ignored)
    summary.update(
        imported=len(good),
        months_created=created_contributions,
        memberships_updated=len(touched_memberships),
        imported_amount=str(total),
        skipped=skipped,
    )

    return summary


# ============================================================
# OPEN CASES
# ============================================================

def _case_summary(rows, ignored: list[str]) -> dict:
    return {
        "total": len(rows),
        "ready": sum(1 for r in rows if r.ok),
        "with_errors": sum(1 for r in rows if not r.ok),
        "ignored_columns": ignored,
        "rows": [
            {
                "line": r.line,
                "member_number": r.values.get("case_number", ""),
                "name": r.values.get("deceased_full_name", ""),
                "plan": "",
                "ok": r.ok,
                "errors": r.errors,
                "warnings": r.warnings,
            }
            for r in rows
        ],
    }


def _case_results(db, current_user, raw: bytes):
    try:
        rows = case_import.read_rows(raw)
    except ImportFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    return case_import.check_rows(
        db, UUID(str(current_user["business_id"])), rows
    )


@router.get("/cases/template")
def cases_template(
    current_user: dict = Depends(require_permission("imports.run")),
):
    return Response(
        content=case_import.template_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="cases-template.csv"'
        },
    )


@router.post("/cases/check")
async def check_cases_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("imports.run")),
):
    """Report what would happen. Saves nothing."""

    rows, ignored = _case_results(db, current_user, await _read(file))

    return _case_summary(rows, ignored)


@router.post("/cases")
async def import_cases_file(
    file: UploadFile = File(...),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("imports.run")),
):
    """Save every case that passed the check, as it stands today."""

    business_id = UUID(str(current_user["business_id"]))
    actor = UUID(str(current_user["user_id"]))

    rows, ignored = _case_results(db, current_user, await _read(file))

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

    created = 0

    for row in rows:
        if not row.ok:
            continue

        db.add(
            FuneralCase(
                business_id=business_id,
                branch_id=branch,
                **row.data,
            )
        )
        created += 1

    skipped = sum(1 for r in rows if not r.ok)

    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor,
        action="import.cases",
        entity_type="import",
        entity_id=None,
        details={
            "filename": (file.filename or "")[:200],
            "cases_created": created,
            "rows_skipped": skipped,
        },
        notes=f"Imported {created} cases from a file.",
    )

    db.commit()

    summary = _case_summary(rows, ignored)
    summary.update(imported=created, skipped=skipped)

    return summary
