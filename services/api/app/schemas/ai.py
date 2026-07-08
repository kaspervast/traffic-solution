"""Pydantic schemas for command center / mitigation draft / citizen vision AI
endpoints (spec sections 10, 11, 14). The predictive-alert schemas
(TrafficAnomaly, WeatherSnapshot, LocalEvent, PredictiveAlertInput/Output,
MitigationAction) live in app/services/gemini_predictive_alert.py per spec
section 13 -- they are imported from there rather than duplicated here.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandQuery(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    operator_id: str | None = None


class EvidenceRow(BaseModel):
    label: str
    value: str
    source: Literal["tomtom", "sumo", "db", "weather", "manual"]


class CommandAnswer(BaseModel):
    intent: str
    answer: str
    evidence: list[EvidenceRow]
    confidence: float = Field(ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    suggested_advisory: str | None = None
    ai_insight_id: uuid.UUID | None = None


class MitigationDraftRequest(BaseModel):
    anomaly_id: uuid.UUID


class MitigationDraftOut(BaseModel):
    ai_insight_id: uuid.UUID
    problem_summary: str
    likely_root_cause: str
    impacted_locations: list[str]
    police_deployment: list[str]
    citizen_advisory_draft: str
    suggested_reroutes: list[str]
    signal_timing_note: str | None
    escalation_priority: Literal["low", "medium", "high", "urgent"]
    confidence: float
    requires_human_approval: bool = True


class CitizenReportVisionRequest(BaseModel):
    image_url: str
    description: str | None = None
    lat: float
    lon: float
    reported_at: dt.datetime | None = None


class CitizenReportVisionOut(BaseModel):
    citizen_report_id: uuid.UUID
    classified_type: Literal[
        "accident", "pothole", "flooding", "obstruction", "roadwork", "crowding", "other"
    ]
    confidence: float
    correlated_flow_anomaly_id: uuid.UUID | None = None
    raw_vision_payload: dict[str, Any]
