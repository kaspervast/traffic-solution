"""Unit tests for deterministic anomaly severity rules (spec section 9)."""

from __future__ import annotations

from app.services.anomaly_service import (
    classify_severity,
    compute_delay_sec,
    compute_speed_ratio,
    evaluate_flow_observation,
)


def test_compute_speed_ratio_normal():
    assert compute_speed_ratio(30.0, 60.0) == 0.5


def test_compute_speed_ratio_handles_missing_values():
    assert compute_speed_ratio(None, 60.0) is None
    assert compute_speed_ratio(30.0, None) is None
    assert compute_speed_ratio(30.0, 0) is None


def test_compute_delay_sec():
    assert compute_delay_sec(500, 300) == 200
    assert compute_delay_sec(None, 300) is None


def test_road_closure_is_always_critical():
    assert classify_severity(road_closure=True, speed_ratio=1.0, delay_sec=0) == "critical"


def test_critical_threshold():
    # speed_ratio <= 0.25 and delay >= 600
    assert classify_severity(road_closure=False, speed_ratio=0.25, delay_sec=600) == "critical"
    assert classify_severity(road_closure=False, speed_ratio=0.20, delay_sec=900) == "critical"


def test_critical_boundary_not_met_falls_to_high():
    # speed_ratio just over 0.25 threshold should not be critical
    assert classify_severity(road_closure=False, speed_ratio=0.26, delay_sec=900) == "high"
    # delay just under 600 with speed_ratio<=0.25 should not be critical
    assert classify_severity(road_closure=False, speed_ratio=0.25, delay_sec=599) == "high"


def test_high_threshold():
    assert classify_severity(road_closure=False, speed_ratio=0.40, delay_sec=300) == "high"
    assert classify_severity(road_closure=False, speed_ratio=0.35, delay_sec=450) == "high"


def test_medium_threshold():
    assert classify_severity(road_closure=False, speed_ratio=0.60, delay_sec=120) == "medium"


def test_low_threshold():
    assert classify_severity(road_closure=False, speed_ratio=0.75, delay_sec=0) == "low"
    assert classify_severity(road_closure=False, speed_ratio=0.70, delay_sec=0) == "low"


def test_normal_when_free_flowing():
    assert classify_severity(road_closure=False, speed_ratio=0.95, delay_sec=10) == "normal"
    assert classify_severity(road_closure=False, speed_ratio=1.0, delay_sec=0) == "normal"


def test_no_speed_ratio_available_defaults_normal_unless_closure():
    assert classify_severity(road_closure=False, speed_ratio=None, delay_sec=None) == "normal"
    assert classify_severity(road_closure=True, speed_ratio=None, delay_sec=None) == "critical"


def test_evaluate_flow_observation_end_to_end():
    result = evaluate_flow_observation(
        current_speed_kmph=11.5,
        free_flow_speed_kmph=42.0,
        current_travel_time_sec=780,
        free_flow_travel_time_sec=300,
        road_closure=False,
    )
    assert result.speed_ratio == 11.5 / 42.0
    assert result.delay_sec == 480
    # ratio ~0.2738 is > 0.25 so the critical rule doesn't match; it does
    # match "speed_ratio <= 0.40 and delay >= 300" -> high.
    assert result.severity == "high"
    assert result.is_anomaly is True


def test_evaluate_flow_observation_normal_traffic_not_anomaly():
    result = evaluate_flow_observation(
        current_speed_kmph=40.0,
        free_flow_speed_kmph=42.0,
        current_travel_time_sec=310,
        free_flow_travel_time_sec=300,
        road_closure=False,
    )
    assert result.severity == "normal"
    assert result.is_anomaly is False


def test_rule_precedence_top_to_bottom():
    # speed_ratio <= 0.25 but delay is low (< 600): should NOT be critical,
    # should fall through to the high-threshold check (0.25 <= 0.40, but
    # delay must be >= 300 for high too) -- here delay=50 fails all
    # thresholds except the plain speed_ratio<=0.75 "low" rule.
    result = classify_severity(road_closure=False, speed_ratio=0.20, delay_sec=50)
    assert result == "low"
