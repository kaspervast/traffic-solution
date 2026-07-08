"""Builds the grounded context dict for Gemini's SUMO scenario-authoring
stage (spec section S, stage 1). This module only reads from the DB -- it
never calls Gemini and never invents a TomTom<->SUMO edge mapping that
doesn't exist. When no approved (or any) mapping exists for the requested
edge, the context explicitly says so via "tomtom_grounding": "unavailable
- no approved edge mapping yet" so the Gemini system prompt (which already
forbids inventing numbers) has an honest signal instead of silence.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    SumoEdge,
    TomTomSumoEdgeMapping,
    TrafficAnomaly,
    TrafficFlowObservation,
    TrafficIncident,
)

RECENT_INCIDENT_WINDOW = dt.timedelta(hours=2)
RECENT_ANOMALY_LIMIT = 10
RECENT_INCIDENT_LIMIT = 20


def _get_edge_mapping(db: Session, sumo_edge_db_id: uuid.UUID) -> TomTomSumoEdgeMapping | None:
    """Prefers an approved mapping; falls back to a pending/manual_override
    mapping (not yet reviewed either way) if no approved one exists yet, so
    the context can still say *something* concrete rather than nothing --
    but the context always records review_status so Gemini/the operator can
    judge trust level, never silently upgrading a pending match to fact.

    Explicitly excludes review_status="rejected": a human already looked at
    that match and said it's wrong, so it must never be surfaced even with
    a caution label -- that would read as "unreviewed" rather than
    "known incorrect"."""
    approved = db.scalar(
        select(TomTomSumoEdgeMapping).where(
            TomTomSumoEdgeMapping.sumo_edge_db_id == sumo_edge_db_id,
            TomTomSumoEdgeMapping.review_status == "approved",
        )
    )
    if approved is not None:
        return approved
    return db.scalar(
        select(TomTomSumoEdgeMapping)
        .where(
            TomTomSumoEdgeMapping.sumo_edge_db_id == sumo_edge_db_id,
            TomTomSumoEdgeMapping.review_status != "rejected",
        )
        .order_by(TomTomSumoEdgeMapping.updated_at.desc())
    )


def build_scenario_context(
    db: Session,
    sumo_edge_id: str,
    network_id: uuid.UUID,
    aoi_id: uuid.UUID,
) -> dict[str, Any]:
    """Returns a JSON-serializable context dict for
    gemini_service.draft_scenario_request(). All facts come from the DB;
    the caller (the /api/sumo/scenarios/draft route) must not add anything
    else to what Gemini sees."""
    now = dt.datetime.now(dt.timezone.utc)
    context: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "sumo_edge_id": sumo_edge_id,
        "network_id": str(network_id),
        "aoi_id": str(aoi_id),
    }

    edge = db.scalar(
        select(SumoEdge).where(
            SumoEdge.network_id == network_id,
            SumoEdge.sumo_edge_id == sumo_edge_id,
        )
    )
    if edge is None:
        context["sumo_edge"] = None
        context["tomtom_grounding"] = "unavailable - sumo_edge_id not found in this network"
        context["recent_incidents"] = []
        context["recent_anomalies"] = []
        return context

    context["sumo_edge"] = {
        "sumo_edge_id": edge.sumo_edge_id,
        "road_name": edge.road_name,
        "num_lanes": edge.num_lanes,
        "length_m": edge.length_m,
        "speed_mps": edge.speed_mps,
    }

    mapping = _get_edge_mapping(db, edge.id)
    if mapping is None:
        context["tomtom_grounding"] = "unavailable - no approved edge mapping yet"
        context["tomtom_mapping"] = None
        context["latest_flow_observation"] = None
    else:
        context["tomtom_mapping"] = {
            "review_status": mapping.review_status,
            "match_method": mapping.match_method,
            "distance_m": mapping.distance_m,
            "confidence": mapping.confidence,
        }
        if mapping.review_status != "approved":
            context["tomtom_grounding"] = (
                f"caution - mapping exists but review_status={mapping.review_status}, not yet approved"
            )
        else:
            context["tomtom_grounding"] = "available"

        latest_obs = db.scalar(
            select(TrafficFlowObservation)
            .where(TrafficFlowObservation.road_segment_id == mapping.road_segment_id)
            .order_by(TrafficFlowObservation.observed_at.desc())
        )
        if latest_obs is None:
            context["latest_flow_observation"] = None
        else:
            context["latest_flow_observation"] = {
                "observed_at": latest_obs.observed_at.isoformat(),
                "current_speed_kmph": latest_obs.current_speed_kmph,
                "free_flow_speed_kmph": latest_obs.free_flow_speed_kmph,
                "speed_ratio": latest_obs.speed_ratio,
                "delay_sec": latest_obs.delay_sec,
                "road_closure": latest_obs.road_closure,
            }

    incident_cutoff = now - RECENT_INCIDENT_WINDOW
    incidents = db.scalars(
        select(TrafficIncident)
        .where(
            TrafficIncident.aoi_id == aoi_id,
            TrafficIncident.is_active.is_(True),
            TrafficIncident.last_seen_at >= incident_cutoff,
        )
        .order_by(TrafficIncident.last_seen_at.desc())
        .limit(RECENT_INCIDENT_LIMIT)
    )
    context["recent_incidents"] = [
        {
            "provider_incident_id": i.provider_incident_id,
            "category": i.category,
            "magnitude_of_delay": i.magnitude_of_delay,
            "from_text": i.from_text,
            "to_text": i.to_text,
            "description": i.description,
            "delay_sec": i.delay_sec,
            "last_seen_at": i.last_seen_at.isoformat(),
        }
        for i in incidents
    ]

    anomalies = db.scalars(
        select(TrafficAnomaly)
        .where(
            TrafficAnomaly.aoi_id == aoi_id,
            TrafficAnomaly.status == "open",
        )
        .order_by(TrafficAnomaly.detected_at.desc())
        .limit(RECENT_ANOMALY_LIMIT)
    )
    context["recent_anomalies"] = [
        {
            "anomaly_type": a.anomaly_type,
            "severity": a.severity,
            "detected_at": a.detected_at.isoformat(),
            "baseline_speed_kmph": a.baseline_speed_kmph,
            "observed_speed_kmph": a.observed_speed_kmph,
            "delay_sec": a.delay_sec,
        }
        for a in anomalies
    ]

    return context
