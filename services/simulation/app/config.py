"""Configuration for the SUMO simulation service.

Reads from environment variables / repo-root .env. Also resolves SUMO_HOME
and makes sumolib/traci importable from SUMO's tools/ directory, which is
how SUMO ships its Python bindings (they are not a normal pip package).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_THIS_FILE = Path(__file__).resolve()
# services/simulation/app/config.py -> repo root is 3 parents up
_REPO_ROOT = _THIS_FILE.parents[3]
_REPO_ROOT_ENV = _REPO_ROOT / ".env"


class SimulationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT_ENV) if _REPO_ROOT_ENV.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sumo_home: str = r"C:\Program Files (x86)\Eclipse\Sumo"
    sumo_binary: str = "sumo"
    database_url: str = "postgresql+psycopg://traffic:trafficpass@localhost:5566/trafficdb"
    redis_url: str = "redis://localhost:6379/0"
    sumo_scenario_dir: str = str(_REPO_ROOT / "services/simulation/scenarios/rajkot_pilot")
    sumo_runs_dir: str = str(_REPO_ROOT / "services/simulation/runs")
    sumo_default_duration_seconds: int = 3600
    sumo_default_seed: int = 42


def get_simulation_settings() -> SimulationSettings:
    return SimulationSettings()


def ensure_sumo_tools_on_path(sumo_home: str | None = None) -> str:
    """Appends SUMO_HOME/tools to sys.path so `import sumolib` / `import
    traci` work, and returns the resolved SUMO_HOME. SUMO ships its Python
    helper libraries inside the install tree rather than on PyPI."""
    home = sumo_home or os.environ.get("SUMO_HOME") or get_simulation_settings().sumo_home
    os.environ.setdefault("SUMO_HOME", home)
    tools_dir = str(Path(home) / "tools")
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    return home
