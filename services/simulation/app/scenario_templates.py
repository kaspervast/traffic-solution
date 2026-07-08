"""Scenario config builders for the ScenarioType variants defined in
services/api/app/schemas/sumo.py (spec section I).

These build the plain-dict `scenario_config` payload that
SumoScenarioRunner.run_scenario() and TraciScenarioRunner both consume
(edge_changes / signal_changes / demand_changes lists), so the same
templates work for both the synchronous static-file runner and the TraCI
runtime runner.
"""

from __future__ import annotations

from typing import Any


def road_closure(sumo_edge_id: str, start_second: int = 0, end_second: int = 3600) -> dict[str, Any]:
    return {
        "edge_changes": [
            {
                "sumo_edge_id": sumo_edge_id,
                "action": "close",
                "start_second": start_second,
                "end_second": end_second,
            }
        ],
    }


def lane_block(
    sumo_edge_id: str, reduced_lanes: int, start_second: int = 0, end_second: int = 3600
) -> dict[str, Any]:
    return {
        "edge_changes": [
            {
                "sumo_edge_id": sumo_edge_id,
                "action": "reduce_lanes",
                "value": reduced_lanes,
                "start_second": start_second,
                "end_second": end_second,
            }
        ],
    }


def speed_reduction(
    sumo_edge_id: str, new_speed_mps: float, start_second: int = 0, end_second: int = 3600
) -> dict[str, Any]:
    """Used for rain_slowdown and generic congestion scenarios. Requires the
    TraCI runtime runner (traci_runner.py) to take effect -- see the note in
    scenario_runner.py's _write_additional_file."""
    return {
        "edge_changes": [
            {
                "sumo_edge_id": sumo_edge_id,
                "action": "reduce_speed",
                "value": new_speed_mps,
                "start_second": start_second,
                "end_second": end_second,
            }
        ],
    }


def one_way_conversion(sumo_edge_id: str, start_second: int = 0, end_second: int = 3600) -> dict[str, Any]:
    return {
        "edge_changes": [
            {
                "sumo_edge_id": sumo_edge_id,
                "action": "reverse_direction",
                "start_second": start_second,
                "end_second": end_second,
            }
        ],
    }


def signal_timing_change(
    traffic_light_id: str, phase_index: int, new_duration_sec: int
) -> dict[str, Any]:
    return {
        "signal_changes": [
            {
                "traffic_light_id": traffic_light_id,
                "phase_index": phase_index,
                "new_duration_sec": new_duration_sec,
            }
        ],
    }


def event_demand_surge(
    factor: float,
    target_lat: float | None = None,
    target_lon: float | None = None,
    radius_m: int | None = None,
    start_second: int = 0,
    end_second: int = 3600,
) -> dict[str, Any]:
    demand_type = "increase_zone" if target_lat is not None else "increase_global"
    return {
        "demand_changes": [
            {
                "demand_type": demand_type,
                "factor": factor,
                "target_lat": target_lat,
                "target_lon": target_lon,
                "radius_m": radius_m,
                "start_second": start_second,
                "end_second": end_second,
            }
        ],
    }


def rain_slowdown(edge_ids: list[str], speed_factor: float = 0.6) -> dict[str, Any]:
    """Applies a uniform speed reduction across a list of edges to
    approximate rain conditions. MVP heuristic only -- not a calibrated
    weather-impact model."""
    return {
        "edge_changes": [
            {
                "sumo_edge_id": edge_id,
                "action": "reduce_speed",
                "value": "factor",  # interpreted by caller alongside speed_factor
                "start_second": 0,
                "end_second": 3600,
            }
            for edge_id in edge_ids
        ],
        "rain_speed_factor": speed_factor,
    }


def combine(*configs: dict[str, Any]) -> dict[str, Any]:
    """Merges multiple scenario config dicts (edge_changes/signal_changes/
    demand_changes lists get concatenated) for scenario_type='combined'."""
    merged: dict[str, Any] = {"edge_changes": [], "signal_changes": [], "demand_changes": []}
    for cfg in configs:
        for key in ("edge_changes", "signal_changes", "demand_changes"):
            merged[key].extend(cfg.get(key, []))
    return merged
