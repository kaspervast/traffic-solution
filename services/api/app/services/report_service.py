"""Daily/weekly report generation from real stored data (spec sections
12.4, 17). Never returns hardcoded sample numbers -- if there is no data
for the requested period, counts come back as zero/empty, not fabricated.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ProbePoint, TrafficAnomaly, TrafficIncident


def _day_bounds(date: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(date, dt.time.min, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    return start, end


def generate_daily_report(db: Session, date: dt.date) -> dict[str, Any]:
    start, end = _day_bounds(date)

    anomalies = list(
        db.scalars(
            select(TrafficAnomaly).where(
                TrafficAnomaly.detected_at >= start, TrafficAnomaly.detected_at < end
            )
        )
    )
    severity_counts = Counter(a.severity for a in anomalies)

    probe_counts: Counter[str] = Counter()
    probe_ratios: dict[str, list[float]] = {}
    probe_max_delay: dict[str, int] = {}
    for a in anomalies:
        if a.probe_point_id is None:
            continue
        key = str(a.probe_point_id)
        probe_counts[key] += 1
        if a.observed_speed_kmph and a.baseline_speed_kmph:
            ratio = a.observed_speed_kmph / a.baseline_speed_kmph
            probe_ratios.setdefault(key, []).append(ratio)
        if a.delay_sec is not None:
            probe_max_delay[key] = max(probe_max_delay.get(key, 0), a.delay_sec)

    worst_locations = []
    for probe_id, count in probe_counts.most_common(5):
        probe = db.get(ProbePoint, probe_id)
        ratios = probe_ratios.get(probe_id, [])
        worst_locations.append(
            {
                "probe_point_id": probe_id,
                "probe_point_name": probe.name if probe else None,
                "road_name": None,
                "anomaly_count": count,
                "avg_speed_ratio": round(sum(ratios) / len(ratios), 3) if ratios else None,
                "max_delay_sec": probe_max_delay.get(probe_id),
            }
        )

    # Peak windows: bucket anomalies into hourly windows, report the top 3.
    hourly = Counter(a.detected_at.replace(minute=0, second=0, microsecond=0) for a in anomalies)
    peak_windows = [
        {
            "window_start": hour.isoformat(),
            "window_end": (hour + dt.timedelta(hours=1)).isoformat(),
            "anomaly_count": count,
        }
        for hour, count in hourly.most_common(3)
    ]

    incidents = list(
        db.scalars(
            select(TrafficIncident).where(
                TrafficIncident.first_seen_at >= start, TrafficIncident.first_seen_at < end
            )
        )
    )
    incident_summary = {
        "total_incidents": len(incidents),
        "by_category": dict(Counter(str(i.category) for i in incidents)),
    }

    return {
        "date": date.isoformat(),
        "total_anomalies": len(anomalies),
        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
        },
        "worst_locations": worst_locations,
        "peak_windows": peak_windows,
        "incident_summary": incident_summary,
        "weather_events_correlation": None,  # requires weather_snapshots/local_events data
        "ai_executive_summary": None,  # populated by a Gemini call in the router, kept out of this pure DB layer
        "suggested_follow_up_actions": [],
        "is_seed_demo_data": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def generate_weekly_report(db: Session, week_start: dt.date) -> dict[str, Any]:
    week_end = week_start + dt.timedelta(days=7)
    start_dt = dt.datetime.combine(week_start, dt.time.min, tzinfo=dt.timezone.utc)
    end_dt = dt.datetime.combine(week_end, dt.time.min, tzinfo=dt.timezone.utc)

    anomalies = list(
        db.scalars(
            select(TrafficAnomaly).where(
                TrafficAnomaly.detected_at >= start_dt, TrafficAnomaly.detected_at < end_dt
            )
        )
    )
    probe_counts = Counter(str(a.probe_point_id) for a in anomalies if a.probe_point_id)
    repeated_bottlenecks = []
    for probe_id, count in probe_counts.most_common(10):
        if count < 2:
            continue
        probe = db.get(ProbePoint, probe_id)
        repeated_bottlenecks.append(
            {
                "probe_point_id": probe_id,
                "probe_point_name": probe.name if probe else None,
                "road_name": None,
                "anomaly_count": count,
                "avg_speed_ratio": None,
                "max_delay_sec": None,
            }
        )

    incidents = list(
        db.scalars(
            select(TrafficIncident).where(
                TrafficIncident.first_seen_at >= start_dt, TrafficIncident.first_seen_at < end_dt
            )
        )
    )
    incident_type_breakdown = dict(Counter(str(i.category) for i in incidents))

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "repeated_bottlenecks": repeated_bottlenecks,
        "average_speed_trend": [],  # requires daily aggregation job; left empty rather than fabricated
        "delay_trend": [],
        "incident_type_breakdown": incident_type_breakdown,
        "recommendations": [],
        "is_seed_demo_data": False,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
