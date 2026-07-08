"""Deterministic anomaly detection (spec section 9).

Do not rely only on Gemini for anomaly detection -- these are pure,
deterministic rules evaluated against normalized TomTom flow data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["low", "medium", "high", "critical", "normal"]


@dataclass
class AnomalyEvaluation:
    severity: Severity
    speed_ratio: float | None
    delay_sec: int | None
    score: float
    is_anomaly: bool


def compute_speed_ratio(current_speed_kmph: float | None, free_flow_speed_kmph: float | None) -> float | None:
    if current_speed_kmph is None or not free_flow_speed_kmph:
        return None
    return current_speed_kmph / free_flow_speed_kmph


def compute_delay_sec(current_travel_time_sec: int | None, free_flow_travel_time_sec: int | None) -> int | None:
    if current_travel_time_sec is None or free_flow_travel_time_sec is None:
        return None
    return current_travel_time_sec - free_flow_travel_time_sec


def classify_severity(
    *,
    road_closure: bool,
    speed_ratio: float | None,
    delay_sec: int | None,
) -> Severity:
    """Exact severity rule table from spec section 9:

    | Rule | Severity |
    |---|---|
    | roadClosure = true | critical |
    | speed_ratio <= 0.25 and delay >= 600 sec | critical |
    | speed_ratio <= 0.40 and delay >= 300 sec | high |
    | speed_ratio <= 0.60 and delay >= 120 sec | medium |
    | speed_ratio <= 0.75 | low |
    | otherwise | normal |

    Rules are evaluated top-to-bottom; the first match wins.
    """
    if road_closure:
        return "critical"

    if speed_ratio is not None:
        if speed_ratio <= 0.25 and (delay_sec or 0) >= 600:
            return "critical"
        if speed_ratio <= 0.40 and (delay_sec or 0) >= 300:
            return "high"
        if speed_ratio <= 0.60 and (delay_sec or 0) >= 120:
            return "medium"
        if speed_ratio <= 0.75:
            return "low"

    return "normal"


def _severity_score(severity: Severity, speed_ratio: float | None) -> float:
    """A continuous 0-1 "how bad" score for sorting/ranking, derived from
    the severity bucket plus how far speed_ratio is below 1.0. Not part of
    the classification decision itself (that's classify_severity, which is
    the deterministic source of truth) -- purely for ordering anomalies of
    the same severity."""
    base = {"normal": 0.0, "low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}[severity]
    if speed_ratio is None:
        return base
    shortfall = max(0.0, 1.0 - speed_ratio)
    return round(min(1.0, base + shortfall * 0.1), 4)


def evaluate_flow_observation(
    *,
    current_speed_kmph: float | None,
    free_flow_speed_kmph: float | None,
    current_travel_time_sec: int | None,
    free_flow_travel_time_sec: int | None,
    road_closure: bool = False,
) -> AnomalyEvaluation:
    speed_ratio = compute_speed_ratio(current_speed_kmph, free_flow_speed_kmph)
    delay_sec = compute_delay_sec(current_travel_time_sec, free_flow_travel_time_sec)
    severity = classify_severity(road_closure=road_closure, speed_ratio=speed_ratio, delay_sec=delay_sec)
    score = _severity_score(severity, speed_ratio)
    return AnomalyEvaluation(
        severity=severity,
        speed_ratio=speed_ratio,
        delay_sec=delay_sec,
        score=score,
        is_anomaly=severity != "normal",
    )


def build_evidence(
    *,
    probe_point_id: str,
    observed_at: str,
    current_speed_kmph: float | None,
    free_flow_speed_kmph: float | None,
    speed_ratio: float | None,
    delay_sec: int | None,
    confidence: float | None,
    nearby_incidents: list[dict[str, Any]] = field(default_factory=list),
    weather: dict[str, Any] | None = None,
    local_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Builds the minimum anomaly evidence JSON shape from spec section 9."""
    return {
        "probe_point_id": probe_point_id,
        "observed_at": observed_at,
        "current_speed_kmph": current_speed_kmph,
        "free_flow_speed_kmph": free_flow_speed_kmph,
        "speed_ratio": speed_ratio,
        "delay_sec": delay_sec,
        "confidence": confidence,
        "nearby_incidents": nearby_incidents or [],
        "weather": weather or {},
        "local_events": local_events or [],
    }
