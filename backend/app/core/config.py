from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sales Territory Mapping API"
    database_url: str = Field(
        default="postgresql+asyncpg://territory:territory@localhost:55432/territory"
    )
    cors_origins: list[str] = ["http://localhost:65183"]

    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_audience: str = ""
    entra_issuer: str = ""
    auth_disabled_for_local_dev: bool = True

    census_batch_url: str = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
    geocode_chunk_size: int = 10_000
    import_worker_concurrency: int = 1
    assignment_event_retention_days: int = 548

    # prod-msa REST host for live customer location data.
    msa_base_url: str = "https://prod-msa.gcp.atd-us.com"
    msa_timeout_seconds: float = 15.0
    msa_cache_ttl_seconds: int = 300

    # BigQuery metrics source (Phase 2 POC). Eventually replaced by an API call.
    bigquery_project: str = "atd-cdp-prod"
    bq_metrics_cache_ttl_seconds: int = 300
    bq_dc_cache_ttl_seconds: int = 3600

    # MapTiler proxy — API key kept server-side; frontend hits /api/map/* only.
    maptiler_api_key: str = ""
    maptiler_base_url: str = "https://api.maptiler.com"
    maptiler_map_id: str = "streets-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
