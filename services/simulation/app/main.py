"""Rajkot SUMO Simulation Service (spec section O, extended).

Exposes:
  GET  /health
  POST /run-scenario          -- synchronous, OK for short MVP runs (spec O)
  POST /run-scenario/async     -- enqueues via Redis, returns job_id
  GET  /jobs/{job_id}          -- poll async job status
  POST /build-network          -- runs netconvert + validates (spec E)
  GET  /network/{net_file}/edges -- extract WGS84 edges via sumolib (spec G)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import get_simulation_settings
from app.network_builder import (
    build_network_from_osm,
    extract_edges,
    get_network_offset_and_proj,
    validate_network,
)
from app.queue_worker import enqueue_scenario_job, get_job_status
from app.scenario_runner import SumoScenarioRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Rajkot SUMO Simulation Service")

settings = get_simulation_settings()


class RunScenarioRequest(BaseModel):
    scenario_config: dict


class BuildNetworkRequest(BaseModel):
    osm_file: str
    net_file: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "sumo-simulation"}


@app.post("/run-scenario")
def run_scenario(req: RunScenarioRequest):
    """Synchronous scenario execution. For a quick local MVP this is
    acceptable for short simulations (spec section O). For long-running or
    concurrent scenarios, use /run-scenario/async instead."""
    try:
        runner = SumoScenarioRunner(
            base_scenario_dir=settings.sumo_scenario_dir,
            runs_dir=settings.sumo_runs_dir,
            sumo_binary=settings.sumo_binary,
        )
        result = runner.run_scenario(req.scenario_config)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/run-scenario/async")
def run_scenario_async(req: RunScenarioRequest):
    try:
        job_id = enqueue_scenario_job(req.scenario_config)
        return {"job_id": job_id, "status": "queued"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status


@app.post("/build-network")
def build_network(req: BuildNetworkRequest):
    try:
        build_network_from_osm(req.osm_file, req.net_file)
        ok = validate_network(req.net_file)
        return {
            "net_file": req.net_file,
            "validated": ok,
            "location": get_network_offset_and_proj(req.net_file),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/network/edges")
def network_edges(net_file: str):
    try:
        records = extract_edges(net_file)
        return {
            "count": len(records),
            "edges": [
                {
                    "sumo_edge_id": r.sumo_edge_id,
                    "from_node": r.from_node,
                    "to_node": r.to_node,
                    "road_name": r.road_name,
                    "priority": r.priority,
                    "num_lanes": r.num_lanes,
                    "speed_mps": r.speed_mps,
                    "length_m": r.length_m,
                    "lonlat_shape": r.lonlat_shape,
                }
                for r in records
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
