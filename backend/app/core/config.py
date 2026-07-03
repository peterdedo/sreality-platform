from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Environment: "dev" (default, local convenience) or "production". Controls
    # fail-loud behavior for secrets and whether create_all() runs (see app/main.py).
    app_env: str = "dev"

    # Database
    database_url: str = "postgresql+psycopg2://sreality:sreality@localhost:5432/sreality"

    # Redis (job store / cache / scraping-run lock)
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Shared API key guarding state-changing / heavy endpoints (scrape trigger,
    # analytics recompute, exports). In dev it defaults to a well-known value so
    # local work needs no setup; in production an unset/default key is a fatal
    # misconfiguration -- see _validate_production_secrets below.
    api_key: str = "dev-local-key"

    # Scraping
    sreality_base_url: str = "https://www.sreality.cz"
    sreality_api_base: str = "https://www.sreality.cz/api/v1/estates/search"
    sreality_detail_base: str = "https://www.sreality.cz/api/v1/estates"
    scrape_per_page: int = 999
    # Sreality's search API paginates with ``offset`` + ``per_page``, not ``page``.
    # It stops returning new rows after roughly this many offset steps per query.
    scrape_offset_cap: int = 9_900
    max_listings_page_size: int = 1000
    max_map_markers: int = 200_000
    # Safety cap for single-shot export serialization (not an analytics sample).
    max_export_rows: int = 500_000
    scrape_concurrency: int = 8
    scrape_request_delay_seconds: float = 0.25
    scrape_max_retries: int = 5
    scrape_consecutive_failures_before_fallback: int = 5

    # Scheduler
    enable_scheduler: bool = True
    incremental_scrape_cron_hour: str = "*/6"  # every 6 hours
    full_scrape_cron_hour: str = "3"  # once a day at 03:00

    # Analytics
    analytics_snapshot_hour: str = "4"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Fail loud at startup if production is running with dev-default secrets,
        rather than silently accepting a guessable API key / local DB creds."""
        if self.is_production:
            problems = []
            if self.api_key == "dev-local-key":
                problems.append("API_KEY must be set to a non-default value in production")
            if "sreality:sreality@localhost" in self.database_url:
                problems.append("DATABASE_URL must not use the dev default in production")
            if problems:
                raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self


settings = Settings()
