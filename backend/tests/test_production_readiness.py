"""Safe production settings, the scheduler, health checks and headers."""

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app import main as app_main
from app import run_scheduler
from app.config import Settings
from app.run_scheduler import Job, is_due, tick
from app.services import scheduler_state

TZ = ZoneInfo("Africa/Johannesburg")
GOOD_SECRET = "x" * 40


def settings(**over):
    base = dict(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@db/x",
        jwt_secret_key=GOOD_SECRET,
    )
    base.update(over)
    return Settings(**base)


# ------------------------------------------------------------ configuration


def test_development_is_relaxed_and_allows_localhost():
    s = settings()
    assert not s.is_production
    assert "http://localhost:3000" in s.allowed_origins


def test_production_needs_a_strong_secret_and_a_real_https_address():
    ok = settings(
        app_env="production", cors_origins="https://app.example.co.za/"
    )
    assert ok.allowed_origins == ["https://app.example.co.za"]

    for bad in (
        dict(jwt_secret_key="short"),
        dict(jwt_secret_key="change-me-" + "x" * 40),
        dict(cors_origins=""),
        dict(cors_origins="http://app.example.co.za"),
    ):
        params = dict(
            app_env="production", cors_origins="https://app.example.co.za"
        )
        params.update(bad)
        with pytest.raises(ValidationError):
            settings(**params)


def test_production_does_not_trust_localhost():
    s = settings(app_env="production", cors_origins="https://a.example.com")
    assert not any("localhost" in o for o in s.allowed_origins)


# ---------------------------------------------------------------- scheduler


def at(hour, minute=0, day=10):
    return datetime(2026, 11, day, hour, minute, tzinfo=TZ).astimezone(
        timezone.utc
    )


def test_interval_jobs():
    job = Job("x", lambda: "", every_minutes=30)
    now = at(12)
    assert is_due(job, None, now, TZ)
    assert not is_due(job, now - timedelta(minutes=29), now, TZ)
    assert is_due(job, now - timedelta(minutes=30), now, TZ)


def test_daily_job_runs_once_a_day_after_its_hour():
    job = Job("backup", lambda: "", daily_hour=2, window_hours=22)
    assert not is_due(job, None, at(1, 59), TZ)       # too early
    assert is_due(job, None, at(2, 0), TZ)
    assert not is_due(job, at(2, 0), at(2, 30), TZ)   # already ran today
    assert is_due(job, at(2, 0, day=9), at(2, 0), TZ) # ran yesterday


def test_daily_job_catches_up_inside_its_window_only():
    reminders = Job("reminders", lambda: "", daily_hour=7, window_hours=8)
    # Computer was off at 07:00 and woke at 10:00: still sent.
    assert is_due(reminders, None, at(10), TZ)
    # Woke at 22:00: not sent at night; waits for tomorrow morning.
    assert not is_due(reminders, None, at(22), TZ)


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    from app.config import settings as live

    monkeypatch.setattr(live, "backup_dir", str(tmp_path))
    return tmp_path


def test_tick_runs_due_jobs_isolates_failures_and_records_state(state_dir):
    calls = []

    def good():
        calls.append("good")
        return "done"

    def bad():
        calls.append("bad")
        raise RuntimeError("boom")

    jobs = [
        Job("bad", bad, every_minutes=5),
        Job("good", good, every_minutes=5),
    ]
    now = at(12)
    ran = tick(jobs, now)

    assert calls == ["bad", "good"]            # one failure did not stop the rest
    assert ran == {"bad": "boom", "good": "done"}

    saved = json.loads((state_dir / "scheduler.json").read_text())
    assert saved["jobs"]["bad"]["ok"] is False
    assert saved["jobs"]["good"]["ok"] is True

    # Not run again until due.
    assert tick(jobs, now + timedelta(minutes=1)) == {}
    assert calls == ["bad", "good"]
    assert len(tick(jobs, now + timedelta(minutes=6))) == 2


def test_scheduler_state_reports_alive_degraded_and_stale(state_dir):
    assert scheduler_state.read()["state"] == "never"

    now = datetime.now(timezone.utc)
    scheduler_state.save({"heartbeat_at": now.isoformat(), "jobs": {}})
    assert scheduler_state.read()["state"] == "ok"

    scheduler_state.save(
        {"heartbeat_at": now.isoformat(),
         "jobs": {"backup": {"ok": False}}}
    )
    degraded = scheduler_state.read()
    assert degraded["state"] == "degraded" and degraded["failing"] == ["backup"]

    scheduler_state.save(
        {"heartbeat_at": (now - timedelta(minutes=30)).isoformat(),
         "jobs": {}}
    )
    assert scheduler_state.read()["state"] == "stale"


def test_the_real_job_list_covers_everything_recurring(monkeypatch):
    from app.config import settings as live

    names = [j.name for j in run_scheduler.build_jobs()]
    assert names == [
        "lifecycle", "mortuary_alerts", "reminders", "delivery", "stock",
        "archive", "overdue", "backup",
    ]

    monkeypatch.setattr(live, "scheduler_backups_enabled", False)
    assert "backup" not in [j.name for j in run_scheduler.build_jobs()]


# ------------------------------------------------------- health and headers


def test_health_is_green_when_the_database_answers(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy" and body["database"] == "connected"
    assert "scheduler" in body


def test_health_says_503_when_the_database_is_down(client, monkeypatch):
    class Broken:
        def connect(self):
            raise RuntimeError("no database")

    monkeypatch.setattr(app_main, "engine", Broken())
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


def test_security_headers_are_sent(client):
    headers = client.get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"


# ------------------------------------------------------------ registration

BODY = {
    "business_name": "Fresh Funerals",
    "full_name": "Sipho Dlamini",
    "email": "sipho.fresh@example.com",
    "password": "a-long-password",
}


def test_sign_up_stays_open_while_developing(client):
    assert client.get("/auth/registration-status").json() == {"open": True}


def test_on_a_live_system_sign_up_closes_once_a_business_exists(
    client, test_data, monkeypatch
):
    from app.config import settings as live

    monkeypatch.setattr(live, "app_env", "production")
    # test_data already created businesses, so it must be closed.
    assert client.get("/auth/registration-status").json() == {"open": False}
    response = client.post("/auth/register", json=BODY)
    assert response.status_code == 403
    assert "closed" in response.json()["detail"].lower()


def test_sign_up_can_be_forced_either_way(client, test_data, monkeypatch):
    from app.config import settings as live

    monkeypatch.setattr(live, "app_env", "production")
    monkeypatch.setattr(live, "allow_registration", True)
    assert client.get("/auth/registration-status").json() == {"open": True}

    monkeypatch.setattr(live, "app_env", "development")
    monkeypatch.setattr(live, "allow_registration", False)
    assert client.post("/auth/register", json=BODY).status_code == 403


def test_the_command_line_can_still_create_a_business(db, monkeypatch):
    from app import create_owner
    from app.models.user import User

    answers = iter(["Cli Funerals", "Nomsa Cele", "nomsa.cli@example.com"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(
        create_owner.getpass, "getpass", lambda prompt="": "cli-password-1"
    )
    monkeypatch.setattr(create_owner, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    assert create_owner.main() == 0
    user = db.query(User).filter(
        User.email == "nomsa.cli@example.com"
    ).one()
    assert user.role == "main_admin"
