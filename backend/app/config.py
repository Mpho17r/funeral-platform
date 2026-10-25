from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FuneralOS"

    # "development" (default) or "production". Production refuses to start
    # with weak secrets or without a real web address (see validate_production).
    app_env: str = "development"

    # Web addresses allowed to call the API, comma separated, for example
    # "https://app.yourfuneralhome.co.za". Development adds localhost.
    cors_origins: str = ""
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Sign-in protection.
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15

    # Where instant call links point. Anyone with the link can join, so
    # set this to your own Jitsi server for sensitive work.
    call_base_url: str = "https://meet.jit.si"

    # Automatic backups (see docs/BACKUPS_AND_RECOVERY.md).
    backup_dir: str = "backups"
    backup_keep: int = 14

    # Public sign-up. Unset: open in development; in production open only
    # until the first business exists. Set true/false to force it.
    allow_registration: bool | None = None

    # Outgoing email (reminders and notices). Leave smtp_host empty to keep
    # the one-tap manual sending. SMS and WhatsApp stay manual until a
    # provider is connected (see docs/MESSAGE_DELIVERY.md).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    delivery_max_attempts: int = 3

    # Built-in scheduler (python -m app.run_scheduler).
    scheduler_timezone: str = "Africa/Johannesburg"
    scheduler_backup_hour: int = 2       # nightly backup, local time
    scheduler_reminders_hour: int = 7    # daily payment reminders, local time
    scheduler_backups_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def allowed_origins(self) -> list[str]:
        origins = [
            o.strip().rstrip("/")
            for o in self.cors_origins.split(",")
            if o.strip()
        ]
        if not self.is_production:
            origins += ["http://localhost:3000", "http://127.0.0.1:3000"]
        return list(dict.fromkeys(origins))

    @model_validator(mode="after")
    def validate_production(self):
        """A live system must not run with development shortcuts."""
        if not self.is_production:
            return self

        problems = []
        if len(self.jwt_secret_key) < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters")
        if self.jwt_secret_key.lower().startswith(("change", "secret", "test")):
            problems.append("JWT_SECRET_KEY looks like a placeholder")
        origins = [o for o in self.cors_origins.split(",") if o.strip()]
        if not origins:
            problems.append("CORS_ORIGINS must list your web address")
        if any(not o.strip().startswith("https://") for o in origins):
            problems.append("CORS_ORIGINS must use https:// in production")
        if problems:
            raise ValueError(
                "Unsafe production settings: " + "; ".join(problems)
            )
        return self


settings = Settings()
