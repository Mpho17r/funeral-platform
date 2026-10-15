from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FuneralOS"
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Sign-in protection.
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
    )


settings = Settings()
