"""Late work tells the people responsible, once."""

from datetime import datetime, timedelta, timezone

from app.models.case_task import CaseTask, CaseTaskAssignee
from app.models.notification import Notification
from app.services import overdue_alerts
from tests.test_branches import make_case

PAST = datetime.now(timezone.utc) - timedelta(hours=3)


def test_overdue_task_alerts_each_person_once(db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a, b = test_data["manager"], test_data["staff"]
    task = CaseTask(business_id=biz.id, case_id=case.id, title="Late one",
                    status="pending", due_at=PAST)
    task.assignee_rows = [CaseTaskAssignee(user_id=a.id), CaseTaskAssignee(user_id=b.id)]
    done = CaseTask(business_id=biz.id, case_id=case.id, title="Done", status="completed", due_at=PAST)
    future = CaseTask(business_id=biz.id, case_id=case.id, title="Later", status="pending",
                      due_at=datetime.now(timezone.utc) + timedelta(days=1))
    db.add_all([task, done, future])
    db.commit()

    assert overdue_alerts.run(db) == 2
    assert overdue_alerts.run(db) == 0  # not told twice
    rows = db.query(Notification).filter(Notification.kind == "task_overdue").all()
    assert {r.user_id for r in rows} == {a.id, b.id}
    assert all(r.body == "Late one" for r in rows)
