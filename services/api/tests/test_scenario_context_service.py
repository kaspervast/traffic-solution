"""Unit tests for app.services.scenario_context_service.build_scenario_context
(spec section S, stage 1 context builder).

Exercises the graceful-degradation branches -- edge not found, no TomTom
mapping at all, and a mapping that exists but isn't approved yet -- with a
mocked SQLAlchemy Session (no live Postgres/PostGIS required, per the
project's environment constraints). The mock returns plain
types.SimpleNamespace stand-ins for ORM rows since the function only reads
attributes off them, never issues real SQL.
"""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.scenario_context_service import build_scenario_context

NETWORK_ID = uuid.uuid4()
AOI_ID = uuid.uuid4()
EDGE_DB_ID = uuid.uuid4()
NOW = dt.datetime.now(dt.timezone.utc)


def _fake_edge() -> SimpleNamespace:
    return SimpleNamespace(
        id=EDGE_DB_ID,
        sumo_edge_id="edge123",
        road_name="Kalawad Road",
        num_lanes=2,
        length_m=150.0,
        speed_mps=13.9,
    )


def test_edge_not_found_never_fabricates_grounding():
    db = MagicMock()
    db.scalar.side_effect = [None]  # SumoEdge lookup returns nothing

    context = build_scenario_context(db, "does-not-exist", NETWORK_ID, AOI_ID)

    assert context["sumo_edge"] is None
    assert "unavailable" in context["tomtom_grounding"]
    assert context["recent_incidents"] == []
    assert context["recent_anomalies"] == []
    # Only the edge lookup should have run -- no mapping/observation/incident
    # queries should fire once the edge itself can't be found.
    assert db.scalar.call_count == 1
    db.scalars.assert_not_called()


def test_no_mapping_reports_unavailable_grounding_explicitly():
    db = MagicMock()
    # scalar() call order: edge, approved-mapping (None), fallback-mapping (None)
    db.scalar.side_effect = [_fake_edge(), None, None]
    db.scalars.side_effect = [[], []]  # incidents, anomalies

    context = build_scenario_context(db, "edge123", NETWORK_ID, AOI_ID)

    assert context["sumo_edge"]["sumo_edge_id"] == "edge123"
    assert context["sumo_edge"]["road_name"] == "Kalawad Road"
    assert context["tomtom_mapping"] is None
    assert context["tomtom_grounding"] == "unavailable - no approved edge mapping yet"
    assert context["latest_flow_observation"] is None


def test_pending_mapping_is_flagged_as_caution_not_fabricated_as_fact():
    pending_mapping = SimpleNamespace(
        review_status="pending",
        match_method="spatial_nearest",
        distance_m=12.5,
        confidence=0.8,
        road_segment_id=uuid.uuid4(),
    )
    db = MagicMock()
    # scalar() order: edge, approved-mapping(None) -> fallback returns pending
    db.scalar.side_effect = [_fake_edge(), None, pending_mapping, None]
    db.scalars.side_effect = [[], []]

    context = build_scenario_context(db, "edge123", NETWORK_ID, AOI_ID)

    assert context["tomtom_mapping"]["review_status"] == "pending"
    assert "caution" in context["tomtom_grounding"]
    assert "not yet approved" in context["tomtom_grounding"]


def test_approved_mapping_with_flow_observation_is_marked_available():
    approved_mapping = SimpleNamespace(
        review_status="approved",
        match_method="spatial_nearest",
        distance_m=5.0,
        confidence=0.95,
        road_segment_id=uuid.uuid4(),
    )
    flow_obs = SimpleNamespace(
        observed_at=NOW,
        current_speed_kmph=12.0,
        free_flow_speed_kmph=40.0,
        speed_ratio=0.3,
        delay_sec=300,
        road_closure=False,
    )
    db = MagicMock()
    # scalar() order: edge, approved-mapping (found immediately), flow observation
    db.scalar.side_effect = [_fake_edge(), approved_mapping, flow_obs]
    db.scalars.side_effect = [[], []]

    context = build_scenario_context(db, "edge123", NETWORK_ID, AOI_ID)

    assert context["tomtom_grounding"] == "available"
    assert context["latest_flow_observation"]["current_speed_kmph"] == 12.0
    assert context["latest_flow_observation"]["delay_sec"] == 300


def test_recent_incidents_and_anomalies_are_passed_through_verbatim():
    incident = SimpleNamespace(
        provider_incident_id="inc-1",
        category="jam",
        magnitude_of_delay=2,
        from_text="Kalawad Road",
        to_text="150 Feet Ring Road",
        description="Traffic jam",
        delay_sec=300,
        last_seen_at=NOW,
    )
    anomaly = SimpleNamespace(
        anomaly_type="speed_drop",
        severity="high",
        detected_at=NOW,
        baseline_speed_kmph=40.0,
        observed_speed_kmph=12.0,
        delay_sec=300,
    )
    db = MagicMock()
    db.scalar.side_effect = [_fake_edge(), None, None]  # no mapping
    db.scalars.side_effect = [[incident], [anomaly]]

    context = build_scenario_context(db, "edge123", NETWORK_ID, AOI_ID)

    assert len(context["recent_incidents"]) == 1
    assert context["recent_incidents"][0]["provider_incident_id"] == "inc-1"
    assert len(context["recent_anomalies"]) == 1
    assert context["recent_anomalies"][0]["anomaly_type"] == "speed_drop"


def test_context_is_json_serializable():
    import json

    db = MagicMock()
    db.scalar.side_effect = [None]

    context = build_scenario_context(db, "edge123", NETWORK_ID, AOI_ID)
    # Should not raise -- everything in the context must already be
    # JSON-safe since it's handed straight to gemini_service (default=str
    # is only a safety net there, not relied on here).
    json.dumps(context)
