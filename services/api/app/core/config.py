"""Application configuration loaded from environment variables (.env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root .env (services/api/app/core/config.py -> up 4 levels), falling
# back to a local .env if this package is relocated -- e.g. inside a
# container, where only services/api gets copied to /app and there is no
# 5-level-deep parent directory at all (parents[4] would raise IndexError
# rather than just missing the file). In a container, docker-compose's
# `env_file: .env` already injects everything into the process environment,
# so pydantic-settings finds the values via os.environ regardless of
# whether an on-disk .env file is found here.
_PARENTS = Path(__file__).resolve().parents
_REPO_ROOT_ENV = _PARENTS[4] / ".env" if len(_PARENTS) > 4 else None
_ENV_FILE = str(_REPO_ROOT_ENV) if _REPO_ROOT_ENV and _REPO_ROOT_ENV.exists() else ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"

    database_url: str = "postgresql+psycopg://traffic:trafficpass@localhost:5566/trafficdb"
    redis_url: str = "redis://localhost:6379/0"

    tomtom_api_key: str = "replace_me"
    tomtom_base_url: str = "https://api.tomtom.com"
    tomtom_flow_zoom: int = 10
    tomtom_flow_style: str = "absolute"
    tomtom_flow_unit: str = "kmph"

    gemini_api_key: str = "replace_me"
    gemini_model: str = "gemini-3.5-flash"

    aoi_name: str = "Rajkot 1 km Pilot Zone"
    aoi_center_lat: float = 22.329077
    aoi_center_lon: float = 70.769564
    aoi_radius_m: int = 1000
    aoi_bbox: str = "70.759854,22.320094,70.779274,22.338060"

    weather_api_key: str = "replace_me_if_required"
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""

    sumo_home: str = ""
    sumo_service_url: str = "http://localhost:8100"
    sumo_scenario_dir: str = "./services/simulation/scenarios/rajkot_pilot"
    sumo_runs_dir: str = "./services/simulation/runs"
    sumo_default_duration_seconds: int = 3600
    sumo_default_seed: int = 42

    next_public_api_base_url: str = "http://localhost:8000"

    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    @property
    def aoi_bbox_tuple(self) -> tuple[float, float, float, float]:
        """Returns (min_lon, min_lat, max_lon, max_lat)."""
        parts = [float(p) for p in self.aoi_bbox.split(",")]
        return parts[0], parts[1], parts[2], parts[3]


@lru_cache
def get_settings() -> Settings:
    return Settings()
