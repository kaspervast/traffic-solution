"""Rajkot SUMO Simulation Service (spec section O, extended).

Exposes:
  GET  /health
  POST /run-scenario          -- synchronous, OK for short MVP runs (spec O)
  POST /run-scenario/async     -- enqueues via Redis, returns job_id
  GET  /jobs/{job_id}          -- poll async job status
  POST /build-network          -- runs netconvert + validates (spec E)
  GET  /network/{net_file}/edges -- extract WGS84 edges via sumolib (spec G)
  POST /build-scenario         -- OSM download + netconvert + demand generation
                                   for the Network Builder tab (extends spec E)
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import get_simulation_settings
from app.network_builder import (
    build_network_from_osm,
    count_junctions,
    count_vehicles,
    download_osm_extract,
    extract_edges,
    generate_demand,
    get_network_offset_and_proj,
    slugify,
    validate_bbox_size,
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


class BuildScenarioRequest(BaseModel):
    name: str
    bbox: str
    duration_seconds: int = 3600
    demand_period: float = 3.0
    fringe_factor: float = 5.0
    seed: int = 42


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


@app.post("/build-scenario")
def build_scenario(req: BuildScenarioRequest):
    """Full pipeline for the Network Builder tab: Overpass OSM download ->
    netconvert -> validate -> randomTrips.py demand generation. Creates
    scenarios/<slug>/network/ and scenarios/<slug>/demand/ as siblings of
    scenarios/rajkot_pilot/, mirroring exactly how that pilot network was
    built by hand (see scenarios/rajkot_pilot/README.md). Scoped to small
    pilot-style bboxes only (max ~10km per side) -- this is not a city-wide
    extraction tool."""
    try:
        validate_bbox_size(req.bbox)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        slug = slugify(req.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # scenarios/rajkot_pilot lives at settings.sumo_scenario_dir; new
    # scenarios are created as siblings of it under the same parent.
    scenarios_root = Path(settings.sumo_scenario_dir).resolve().parent
    scenario_dir = scenarios_root / slug
    network_dir = scenario_dir / "network"
    demand_dir = scenario_dir / "demand"

    osm_file = network_dir / f"{slug}.osm.xml"
    net_file = network_dir / f"{slug}.net.xml"
    route_file = demand_dir / "baseline.rou.xml"

    try:
        download_osm_extract(req.bbox, str(osm_file))
        build_network_from_osm(str(osm_file), str(net_file))
        validated = validate_network(str(net_file))
        generate_demand(
            str(net_file),
            str(route_file),
            begin=0,
            end=req.duration_seconds,
            period=req.demand_period,
            fringe_factor=req.fringe_factor,
            seed=req.seed,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"build-scenario pipeline failed: {exc}")

    try:
        edge_count = len(extract_edges(str(net_file)))
        junction_count = count_junctions(str(net_file))
        vehicle_count = count_vehicles(str(route_file))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"build-scenario succeeded but post-build inspection failed: {exc}")

    return {
        "name": slug,
        "net_file": str(net_file),
        "osm_file": str(osm_file),
        "route_file": str(route_file),
        "edge_count": edge_count,
        "junction_count": junction_count,
        "vehicle_count": vehicle_count,
        "validated": validated,
    }
