from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "Pact API"
    version: str = "0.1.0"
    debug: bool = os.getenv("PACT_DEBUG", "false").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./pact.db")
    cookie_secure: bool = os.getenv("PACT_COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
