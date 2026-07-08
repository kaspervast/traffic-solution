"""Pydantic schemas for AOI, probe points, traffic flow/incidents, anomalies."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["high", "medium", "low"]
Severity = Literal["low", "medium", "high", "critical"]
AnomalyStatus = Literal["open", "acknowledged", "resolved", "dismissed"]


class AOIOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    radius_m: int
    bbox_min_lat: float
    bbox_min_lon: float
    bbox_max_lat: float
    bbox_max_lon: float
    center_lat: float
    center_lon: float
    created_at: dt.datetime


class ProbePointCreate(BaseModel):
    name: str
    lat: float
    lon: float
    priority: Priority = "medium"
    polling_interval_seconds: int = 120
    notes: str | None = None
    is_active: bool = True


class ProbePointUpdate(BaseModel):
    name: str | None = None
    lat: float | None = None
    lon: float | None = None
    priority: Priority | None = None
    polling_interval_seconds: int | None = None
    notes: str | None = None
    is_active: bool | None = None


class ProbePointOut(BaseModel):
    id: uuid.UUID
    name: str
    lat: float
    lon: float
    priority: Priority
    polling_interval_seconds: int
    is_active: bool
    notes: str | None = None
    road_segment_id: uuid.UUID | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class FlowObservationOut(BaseModel):
    id: uuid.UUID
    probe_point_id: uuid.UUID | None
    observed_at: dt.datetime
    current_speed_kmph: float | None
    free_flow_speed_kmph: float | None
    current_travel_time_sec: int | None
    free_flow_travel_time_sec: int | None
    speed_ratio: float | None
    delay_sec: int | None
    confidence: float | None
    road_closure: bool


class IncidentOut(BaseModel):
    id: uuid.UUID
    provider_incident_id: str
    category: str | None
    icon_category: int | None
    magnitude_of_delay: int | None
    from_text: str | None
    to_text: str | None
    description: str | None
    delay_sec: int | None
    length_m: float | None
    start_time: dt.datetime | None
    end_time: dt.datetime | None
    is_active: bool
    last_seen_at: dt.datetime
    lat: float | None = None
    lon: float | None = None


class AnomalyOut(BaseModel):
    id: uuid.UUID
    probe_point_id: uuid.UUID | None
    road_segment_id: uuid.UUID | None
    detected_at: dt.datetime
    anomaly_type: str
    severity: Severity
    score: float
    baseline_speed_kmph: float | None
    observed_speed_kmph: float | None
    delay_sec: int | None
    evidence: dict
    status: AnomalyStatus


class AnomalyStatusUpdate(BaseModel):
    status: AnomalyStatus


class IngestionRunResult(BaseModel):
    started_at: dt.datetime
    finished_at: dt.datetime
    probe_points_polled: int
    flow_observations_stored: int
    incidents_upserted: int
    anomalies_detected: int
    errors: list[str] = Field(default_factory=list)
