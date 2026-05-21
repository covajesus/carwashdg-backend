from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CarWash DG API"
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:3000"
    database_url: str = "mysql+pymysql://root@localhost:3306/carwashdg"
    jwt_secret_key: str = "change-me-in-production-use-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    default_admin_email: str = "admin@carwashdg.com"
    default_admin_password: str = "123456789"

    @property
    def cors_origins_list(self) -> list[str]:
        """Accept origins in .env with or without trailing slash."""
        origins: list[str] = []
        for raw in self.cors_origins.split(","):
            base = raw.strip()
            if not base:
                continue
            normalized = base.rstrip("/")
            for candidate in (normalized, f"{normalized}/"):
                if candidate not in origins:
                    origins.append(candidate)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
