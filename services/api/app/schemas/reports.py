"""Pydantic schemas for daily/weekly reports (spec sections 12.4, 17)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel


class SeverityCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class WorstLocation(BaseModel):
    probe_point_id: str | None
    probe_point_name: str | None
    road_name: str | None
    anomaly_count: int
    avg_speed_ratio: float | None
    max_delay_sec: int | None


class PeakWindow(BaseModel):
    window_start: dt.datetime
    window_end: dt.datetime
    anomaly_count: int


class DailyReportOut(BaseModel):
    date: dt.date
    total_anomalies: int
    severity_counts: SeverityCounts
    worst_locations: list[WorstLocation]
    peak_windows: list[PeakWindow]
    incident_summary: dict[str, Any]
    weather_events_correlation: str | None
    ai_executive_summary: str | None
    suggested_follow_up_actions: list[str]
    is_seed_demo_data: bool = False
    generated_at: dt.datetime


class WeeklyReportOut(BaseModel):
    week_start: dt.date
    week_end: dt.date
    repeated_bottlenecks: list[WorstLocation]
    average_speed_trend: list[dict[str, Any]]
    delay_trend: list[dict[str, Any]]
    incident_type_breakdown: dict[str, int]
    recommendations: list[str]
    is_seed_demo_data: bool = False
    generated_at: dt.datetime
