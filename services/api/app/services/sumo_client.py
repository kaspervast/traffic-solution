"""HTTP client for the SUMO simulation service (spec section C: "Main API
stores metrics and exposes results", the simulation service does the actual
SUMO execution)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class SumoServiceClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or get_settings().sumo_service_url).rstrip("/")

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/health")
            r.raise_for_status()
            return r.json()

    async def run_scenario(self, scenario_config: dict[str, Any], timeout_sec: float = 200.0) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            r = await client.post(f"{self.base_url}/run-scenario", json={"scenario_config": scenario_config})
            r.raise_for_status()
            return r.json()

    async def run_scenario_async(self, scenario_config: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(f"{self.base_url}/run-scenario/async", json={"scenario_config": scenario_config})
            r.raise_for_status()
            return r.json()

    async def job_status(self, job_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/jobs/{job_id}")
            r.raise_for_status()
            return r.json()

    async def network_edges(self, net_file: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(f"{self.base_url}/network/edges", params={"net_file": net_file})
            r.raise_for_status()
            return r.json()
