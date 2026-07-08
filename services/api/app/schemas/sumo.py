"""SUMO scenario schema (spec section I, exact base code)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScenarioType = Literal[
    "road_closure",
    "lane_block",
    "one_way_conversion",
    "signal_timing_change",
    "event_demand_surge",
    "rain_slowdown",
    "combined",
]


class SumoEdgeChange(BaseModel):
    sumo_edge_id: str
    action: Literal["close", "reduce_speed", "reduce_lanes", "reverse_direction", "capacity_factor"]
    value: float | str | None = None
    start_second: int = 0
    end_second: int = 3600


class SignalTimingChange(BaseModel):
    traffic_light_id: str
    phase_index: int
    new_duration_sec: int = Field(ge=5, le=180)


class DemandChange(BaseModel):
    demand_type: Literal["increase_global", "increase_zone", "add_event_arrivals"]
    factor: float = Field(default=1.0, ge=0.1, le=5.0)
    target_lat: float | None = None
    target_lon: float | None = None
    radius_m: int | None = None
    start_second: int = 0
    end_second: int = 3600


class SumoScenarioRequest(BaseModel):
    name: str
    scenario_type: ScenarioType
    aoi_id: str
    network_id: str
    simulation_start_second: int = 0
    simulation_end_second: int = 3600
    random_seed: int = 42
    edge_changes: list[SumoEdgeChange] = []
    signal_changes: list[SignalTimingChange] = []
    demand_changes: list[DemandChange] = []
    description: str | None = None
    created_by: str | None = None


class SumoRunMetricsOut(BaseModel):
    total_departed: int | None = None
    total_arrived: int | None = None
    total_loaded: int | None = None
    completed_ratio: float | None = None
    average_travel_time_sec: float | None = None
    average_waiting_time_sec: float | None = None
    average_time_loss_sec: float | None = None
    total_time_loss_sec: float | None = None
    average_speed_mps: float | None = None
    total_teleports: int | None = None


class EdgeImpact(BaseModel):
    sumo_edge_id: str
    road_name: str | None = None
    speed_change_percent: float | None = None
    waiting_time_change_sec: float | None = None
    impact: Literal["better", "worse", "unchanged"]


class OverallDelta(BaseModel):
    average_travel_time_change_percent: float | None = None
    average_waiting_time_change_percent: float | None = None
    completed_ratio_change_percent: float | None = None
    teleport_delta: int | None = None


class ScenarioComparisonOut(BaseModel):
    scenario_id: str
    baseline_run_id: str
    scenario_run_id: str
    overall_delta: OverallDelta
    edge_impacts: list[EdgeImpact]
    recommendation: Literal["approve_for_field_review", "reject", "needs_more_data"]
