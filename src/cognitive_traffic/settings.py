from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import dotenv_values
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: str = "development"
    kafka_bootstrap_servers: str = "localhost:9092"
    object_store_uri: str = "s3://cognitive-traffic"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/traffic_analytics"
    redis_url: str = "redis://localhost:6380/0"
    mlflow_tracking_uri: str = "http://localhost:5000"
    model_name: str = "traffic-speed-quantiles"
    allowed_lateness_seconds: int = Field(default=300, ge=0)
    feature_version: str = "1"
    schema_version: str = "1"


@lru_cache(maxsize=1)
def get_settings() -> PlatformSettings:
    environment_name = os.environ.get("ENVIRONMENT", "development")
    path = Path(os.environ.get("PLATFORM_CONFIG", f"configs/{environment_name}.yaml"))
    configured = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    settings = PlatformSettings(**(configured or {}))
    # Environment variables remain authoritative over checked-in developer defaults.
    environment = PlatformSettings()
    configured_environment = set(os.environ) | set(dotenv_values(".env"))
    overrides = {
        name: getattr(environment, name)
        for name in PlatformSettings.model_fields
        if name.upper() in configured_environment
    }
    return settings.model_copy(update=overrides)
