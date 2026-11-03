"""Is the database up to date with the code?

After an update the database has to be brought forward with
`python3 -m alembic upgrade head`. If that step is skipped the app
half-works in confusing ways, so the answer is shown on /health and logged
when the server starts.
"""

import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

log = logging.getLogger("linda.schema")

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def code_heads() -> set[str]:
    config = Config(str(_ALEMBIC_INI))
    return set(ScriptDirectory.from_config(config).get_heads())


def database_revisions(engine) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version"))
        return {row[0] for row in rows}


def schema_state(engine) -> str:
    """"current", "out_of_date" or "unknown"."""
    try:
        return "current" if database_revisions(engine) == code_heads() else "out_of_date"
    except Exception:
        # No alembic_version table (never migrated) counts as out of date;
        # anything else (files missing in a slim image) we cannot judge.
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
        except Exception:
            return "out_of_date"
        return "unknown"


def warn_if_out_of_date(engine) -> None:
    if schema_state(engine) == "out_of_date":
        log.error(
            "The database is behind the code. Run "
            "`python3 -m alembic upgrade head` then "
            "`python3 -m app.seed_permissions`, and restart."
        )
