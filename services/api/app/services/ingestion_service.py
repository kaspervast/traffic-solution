"""Ingestion worker core logic (spec sections 5, 6).

Polls TomTom flow segment data for all active probe points plus the AOI
incident bbox, normalizes, stores raw + normalized records, and runs the
deterministic anomaly detector on each fresh flow observation. Designed to
be called both by the APScheduler-driven job (app/jobs/poll_tomtom.py) and
by the manual "run-now" API endpoint (POST /api/ingestion/run-now).
"""

from __future__ import annotations

import datetime as dt
import logging

from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AreaOfInterest,
    ProbePoint,
    TrafficAnomaly,
    TrafficFlowObservation,
    TrafficIncident,
)
from app.schemas.traffic import IngestionRunResult
from app.services.anomaly_service import build_evidence, evaluate_flow_observation
from app.services.tomtom_client import TomTomClient, normalize_flow_segment, normalize_incidents

logger = logging.getLogger(__name__)


async def run_ingestion_once(db: Session) -> IngestionRunResult:
    settings = get_settings()
    started_at = dt.datetime.now(dt.timezone.utc)
    errors: list[str] = []
    flow_stored = 0
    incidents_upserted = 0
    anomalies_detected = 0

    aoi = db.scalar(select(AreaOfInterest).order_by(AreaOfInterest.created_at.desc()).limit(1))
    probes = list(db.scalars(select(ProbePoint).where(ProbePoint.is_active.is_(True))))

    async with TomTomClient() as client:
        for probe in probes:
            try:
                point = to_shape(probe.geom)
                raw = await client.get_flow_segment(point.y, point.x)
                norm = normalize_flow_segment(raw)

                coords = norm.get("coordinates") or []
                geom = None
                if len(coords) >= 2:
                    wkt = "LINESTRING(" + ", ".join(
                        f"{c['longitude']} {c['latitude']}" for c in coords
                    ) + ")"
                    geom = WKTElement(wkt, srid=4326)

                observed_at = dt.datetime.now(dt.timezone.utc)
                observation = TrafficFlowObservation(
                    probe_point_id=probe.id,
                    road_segment_id=probe.road_segment_id,
                    observed_at=observed_at,
                    current_speed_kmph=norm["current_speed_kmph"],
                    free_flow_speed_kmph=norm["free_flow_speed_kmph"],
                    current_travel_time_sec=norm["current_travel_time_sec"],
                    free_flow_travel_time_sec=norm["free_flow_travel_time_sec"],
                    speed_ratio=norm["speed_ratio"],
                    delay_sec=norm["delay_sec"],
                    confidence=norm["confidence"],
                    road_closure=norm["road_closure"],
                    geom=geom,
                    raw=norm["raw"],
                )
                db.add(observation)
                flow_stored += 1

                evaluation = evaluate_flow_observation(
                    current_speed_kmph=norm["current_speed_kmph"],
                    free_flow_speed_kmph=norm["free_flow_speed_kmph"],
                    current_travel_time_sec=norm["current_travel_time_sec"],
                    free_flow_travel_time_sec=norm["free_flow_travel_time_sec"],
                    road_closure=norm["road_closure"],
                )
                if evaluation.is_anomaly:
                    evidence = build_evidence(
                        probe_point_id=str(probe.id),
                        observed_at=observed_at.isoformat(),
                        current_speed_kmph=norm["current_speed_kmph"],
                        free_flow_speed_kmph=norm["free_flow_speed_kmph"],
                        speed_ratio=evaluation.speed_ratio,
                        delay_sec=evaluation.delay_sec,
                        confidence=norm["confidence"],
                    )
                    anomaly = TrafficAnomaly(
                        aoi_id=probe.aoi_id,
                        road_segment_id=probe.road_segment_id,
                        probe_point_id=probe.id,
                        detected_at=observed_at,
                        anomaly_type="slowdown",
                        severity=evaluation.severity,
                        score=evaluation.score,
                        baseline_speed_kmph=norm["free_flow_speed_kmph"],
                        observed_speed_kmph=norm["current_speed_kmph"],
                        delay_sec=evaluation.delay_sec,
                        evidence=evidence,
                        status="open",
                    )
                    db.add(anomaly)
                    anomalies_detected += 1
            except Exception as exc:  # keep polling remaining probes even if one fails
                logger.exception("Ingestion failed for probe %s", probe.id)
                errors.append(f"probe {probe.id} ({probe.name}): {exc}")

        if aoi is not None:
            try:
                min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox_tuple
                raw_incidents = await client.get_incidents_for_bbox(min_lon, min_lat, max_lon, max_lat)
                for inc in normalize_incidents(raw_incidents):
                    incidents_upserted += _upsert_incident(db, aoi.id, inc)
            except Exception as exc:
                logger.exception("Incident ingestion failed")
                errors.append(f"incidents: {exc}")

    db.commit()
    finished_at = dt.datetime.now(dt.timezone.utc)
    return IngestionRunResult(
        started_at=started_at,
        finished_at=finished_at,
        probe_points_polled=len(probes),
        flow_observations_stored=flow_stored,
        incidents_upserted=incidents_upserted,
        anomalies_detected=anomalies_detected,
        errors=errors,
    )


def _upsert_incident(db: Session, aoi_id, inc: dict) -> int:
    existing = db.scalar(
        select(TrafficIncident).where(
            TrafficIncident.provider == "tomtom",
            TrafficIncident.provider_incident_id == inc["provider_incident_id"],
        )
    )
    now = dt.datetime.now(dt.timezone.utc)
    geom = None
    geometry = inc.get("geometry") or {}
    if geometry.get("type") == "Point" and geometry.get("coordinates"):
        lon, lat = geometry["coordinates"][:2]
        geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
    elif geometry.get("type") == "LineString" and geometry.get("coordinates"):
        coords = geometry["coordinates"]
        wkt = "LINESTRING(" + ", ".join(f"{c[0]} {c[1]}" for c in coords) + ")"
        geom = WKTElement(wkt, srid=4326)

    if existing:
        existing.last_seen_at = now
        existing.magnitude_of_delay = inc.get("magnitude_of_delay")
        existing.delay_sec = inc.get("delay_sec")
        existing.description = inc.get("description")
        existing.is_active = True
        existing.raw = inc["raw"]
        return 0

    incident = TrafficIncident(
        provider="tomtom",
        provider_incident_id=inc["provider_incident_id"],
        aoi_id=aoi_id,
        first_seen_at=now,
        last_seen_at=now,
        category=str(inc.get("category")) if inc.get("category") is not None else None,
        icon_category=inc.get("icon_category"),
        magnitude_of_delay=inc.get("magnitude_of_delay"),
        probability_of_occurrence=inc.get("probability_of_occurrence"),
        number_of_reports=inc.get("number_of_reports"),
        from_text=inc.get("from_text"),
        to_text=inc.get("to_text"),
        road_numbers=inc.get("road_numbers") or [],
        length_m=inc.get("length_m"),
        delay_sec=inc.get("delay_sec"),
        description=inc.get("description"),
        geom=geom,
        raw=inc["raw"],
        is_active=True,
    )
    db.add(incident)
    return 1
