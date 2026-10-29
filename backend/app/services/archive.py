"""The archive: finished work leaves the working lists.

* Tasks and cases that are finished are archived, by hand or
  automatically a set number of days after they finish. Nothing is
  deleted; archived items can be searched and restored.
* The main admin may let the platform delete archived items a set number
  of months after archiving, or delete one by hand. Records the law or
  the books depend on (a case with quotes, invoices, payments or claims)
  are never deleted: the database refuses, and the item stays archived.
"""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.case_service import CaseService
from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase
from app.services.audit_service import create_audit_log
from app.services.case_archival import ARCHIVABLE_CASE_STATUSES, archive_case

TASK_FILES = Path("storage/task_files")


class ArchiveError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ tasks


def archive_task(db: Session, task: CaseTask, user_id: UUID | None) -> CaseTask:
    if task.archived_at is not None:
        raise ArchiveError(409, "This task is already archived.")
    if task.status != "completed":
        raise ArchiveError(409, "Only finished tasks can be archived.")
    task.archived_at = _now()
    task.archived_by = user_id
    create_audit_log(
        db,
        business_id=task.business_id,
        user_id=user_id,
        action="case.task_archived",
        entity_type="case_task",
        entity_id=task.id,
        details={"title": task.title},
        notes="Task archived.",
    )
    return task


def restore_task(db: Session, task: CaseTask, user_id: UUID | None) -> CaseTask:
    if task.archived_at is None:
        raise ArchiveError(409, "This task is not archived.")
    task.archived_at = None
    task.archived_by = None
    create_audit_log(
        db,
        business_id=task.business_id,
        user_id=user_id,
        action="case.task_restored",
        entity_type="case_task",
        entity_id=task.id,
        details={"title": task.title},
        notes="Task restored from the archive.",
    )
    return task


def delete_archived_task(db: Session, task: CaseTask, user_id: UUID | None) -> None:
    if task.archived_at is None:
        raise ArchiveError(409, "Only archived tasks can be deleted.")
    business_id, task_id, title = task.business_id, task.id, task.title
    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="case.task_purged",
        entity_type="case_task",
        entity_id=task_id,
        details={"title": title},
        notes="Archived task deleted for good.",
    )
    db.delete(task)
    db.flush()
    shutil.rmtree(TASK_FILES / str(business_id) / str(task_id), ignore_errors=True)


# ------------------------------------------------------------------ services
# Services are part of what a family was charged, so they are archived and
# restored but never deleted.


def archive_service(db: Session, service: CaseService, user_id: UUID | None):
    if service.archived_at is not None:
        raise ArchiveError(409, "This service is already archived.")
    if service.status not in ("completed", "cancelled"):
        raise ArchiveError(409, "Only finished services can be archived.")
    service.archived_at = _now()
    service.archived_by = user_id
    create_audit_log(
        db,
        business_id=service.business_id,
        user_id=user_id,
        action="case.service_archived",
        entity_type="case_service",
        entity_id=service.id,
        details={"service": service.service_name},
        notes="Service archived.",
    )
    return service


def restore_service(db: Session, service: CaseService, user_id: UUID | None):
    if service.archived_at is None:
        raise ArchiveError(409, "This service is not archived.")
    service.archived_at = None
    service.archived_by = None
    create_audit_log(
        db,
        business_id=service.business_id,
        user_id=user_id,
        action="case.service_restored",
        entity_type="case_service",
        entity_id=service.id,
        details={"service": service.service_name},
        notes="Service restored from the archive.",
    )
    return service


# ------------------------------------------------------------------ cases


def delete_archived_case(
    db: Session, case: FuneralCase, user_id: UUID | None
) -> None:
    if not case.is_archived:
        raise ArchiveError(409, "Only archived cases can be deleted.")
    business_id, case_id, name = case.business_id, case.id, case.deceased_full_name
    try:
        with db.begin_nested():
            db.delete(case)
            db.flush()
    except IntegrityError:
        raise ArchiveError(
            409,
            "This case has quotes, invoices, payments or claims, which must "
            "be kept for your records, so it cannot be deleted.",
        )
    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="case.purged",
        entity_type="case",
        entity_id=case_id,
        details={"deceased": name},
        notes="Archived case deleted for good.",
    )


# ------------------------------------------------------------------ the sweep


def sweep(db: Session, business: Business, now: datetime | None = None) -> dict:
    """Archive what has finished, and delete what is past its retention."""

    now = now or _now()
    done = {"tasks_archived": 0, "services_archived": 0, "cases_archived": 0, "deleted": 0, "kept": 0}

    days = business.archive_after_days or 0
    if days > 0:
        cutoff = now - timedelta(days=days)
        for task in (
            db.query(CaseTask)
            .filter(
                CaseTask.business_id == business.id,
                CaseTask.status == "completed",
                CaseTask.archived_at.is_(None),
                CaseTask.completed_at.is_not(None),
                CaseTask.completed_at < cutoff,
            )
            .all()
        ):
            archive_task(db, task, None)
            done["tasks_archived"] += 1
        for service in (
            db.query(CaseService)
            .filter(
                CaseService.business_id == business.id,
                CaseService.archived_at.is_(None),
                CaseService.status.in_(("completed", "cancelled")),
                CaseService.updated_at < cutoff,
            )
            .all()
        ):
            archive_service(db, service, None)
            done["services_archived"] += 1
        for case in (
            db.query(FuneralCase)
            .filter(
                FuneralCase.business_id == business.id,
                FuneralCase.is_archived.is_(False),
                FuneralCase.status.in_(tuple(ARCHIVABLE_CASE_STATUSES)),
                FuneralCase.updated_at < cutoff,
            )
            .all()
        ):
            archive_case(db, case=case, business_id=business.id, user_id=None)
            done["cases_archived"] += 1

    months = business.delete_archived_after_months
    if months:
        cutoff = now - timedelta(days=30 * months)
        for task in (
            db.query(CaseTask)
            .filter(
                CaseTask.business_id == business.id,
                CaseTask.archived_at.is_not(None),
                CaseTask.archived_at < cutoff,
            )
            .all()
        ):
            delete_archived_task(db, task, None)
            done["deleted"] += 1
        for case in (
            db.query(FuneralCase)
            .filter(
                FuneralCase.business_id == business.id,
                FuneralCase.is_archived.is_(True),
                FuneralCase.archived_at < cutoff,
            )
            .all()
        ):
            try:
                delete_archived_case(db, case, None)
                done["deleted"] += 1
            except ArchiveError:
                done["kept"] += 1

    db.commit()
    return done


def sweep_all(db: Session) -> dict:
    total = {"tasks_archived": 0, "services_archived": 0, "cases_archived": 0, "deleted": 0, "kept": 0}
    for business in db.query(Business).filter(Business.is_active.is_(True)).all():
        # The sweep runs for the whole business, not one branch.
        db.info.pop("branch_scope", None)
        result = sweep(
            db,
            business,
        )
        for key, value in result.items():
            total[key] += value
    return total
