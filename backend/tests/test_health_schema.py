from app.services import schema_check


def test_health_reports_the_schema_state(client):
    body = client.get("/health").json()

    assert body["schema"] in {"current", "out_of_date", "unknown"}


def test_a_database_behind_the_code_is_called_out_of_date(monkeypatch):
    monkeypatch.setattr(schema_check, "code_heads", lambda: {"newer"})
    monkeypatch.setattr(schema_check, "database_revisions", lambda e: {"older"})

    assert schema_check.schema_state(object()) == "out_of_date"


def test_a_matching_database_is_current(monkeypatch):
    monkeypatch.setattr(schema_check, "code_heads", lambda: {"same"})
    monkeypatch.setattr(schema_check, "database_revisions", lambda e: {"same"})

    assert schema_check.schema_state(object()) == "current"
