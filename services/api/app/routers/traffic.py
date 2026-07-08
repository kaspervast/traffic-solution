"""Live traffic + history + manual ingestion trigger (spec section 11)."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import TrafficFlowObservation
from app.db.session import get_db
from app.schemas.traffic import FlowObservationOut, IngestionRunResult
from app.services.ingestion_service import run_ingestion_once
from app.services.tomtom_client import TomTomClient, normalize_incidents

router = APIRouter(tags=["traffic"])

# Same pilot-scope guardrail used by the simulation service's bbox
# validation for /build-scenario: this ad-hoc lookup is for small
# Network-Builder-style areas, not city-wide queries.
MAX_BBOX_SUMMARY_DEGREES = 0.1

MAGNITUDE_OF_DELAY_LABELS = {
    0: "unknown",
    1: "minor",
    2: "moderate",
    3: "major",
    4: "undefined_or_closure",
}


def _to_out(o: TrafficFlowObservation) -> FlowObservationOut:
    return FlowObservationOut(
        id=o.id,
        probe_point_id=o.probe_point_id,
        observed_at=o.observed_at,
        current_speed_kmph=o.current_speed_kmph,
        free_flow_speed_kmph=o.free_flow_speed_kmph,
        current_travel_time_sec=o.current_travel_time_sec,
        free_flow_travel_time_sec=o.free_flow_travel_time_sec,
        speed_ratio=o.speed_ratio,
        delay_sec=o.delay_sec,
        confidence=o.confidence,
        road_closure=o.road_closure,
    )


@router.post("/api/ingestion/run-now", response_model=IngestionRunResult)
async def ingestion_run_now(
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
) -> IngestionRunResult:
    return await run_ingestion_once(db)


@router.get("/api/traffic/live", response_model=list[FlowObservationOut])
def traffic_live(db: Session = Depends(get_db)) -> list[FlowObservationOut]:
    """Latest observation per probe point (naive N+1-free approach: pull the
    most recent row per probe_point_id via a correlated subquery)."""
    latest_ids_subq = (
        select(TrafficFlowObservation.probe_point_id, TrafficFlowObservation.id)
        .distinct(TrafficFlowObservation.probe_point_id)
        .order_by(TrafficFlowObservation.probe_point_id, TrafficFlowObservation.observed_at.desc())
    ).subquery()
    stmt = select(TrafficFlowObservation).join(
        latest_ids_subq, TrafficFlowObservation.id == latest_ids_subq.c.id
    )
    return [_to_out(o) for o in db.scalars(stmt)]


@router.get("/api/traffic/history", response_model=list[FlowObservationOut])
def traffic_history(
    probe_point_id: uuid.UUID,
    from_: dt.datetime | None = Query(default=None, alias="from"),
    to: dt.datetime | None = None,
    db: Session = Depends(get_db),
) -> list[FlowObservationOut]:
    stmt = select(TrafficFlowObservation).where(
        TrafficFlowObservation.probe_point_id == probe_point_id
    )
    if from_ is not None:
        stmt = stmt.where(TrafficFlowObservation.observed_at >= from_)
    if to is not None:
        stmt = stmt.where(TrafficFlowObservation.observed_at <= to)
    stmt = stmt.order_by(TrafficFlowObservation.observed_at.desc()).limit(1000)
    return [_to_out(o) for o in db.scalars(stmt)]


@router.get("/api/traffic/bbox-summary")
async def bbox_summary(
    min_lon: float = Query(...),
    min_lat: float = Query(...),
    max_lon: float = Query(...),
    max_lat: float = Query(...),
):
    """Ad-hoc TomTom incident summary for an arbitrary bbox (unauthenticated
    read-only lookup, mirrors /api/incidents/live) -- lets the Network
    Builder tab show "N active incidents in this area right now" before the
    operator commits to generating a SUMO network for it. Unlike the rest
    of the app, this bbox is NOT the fixed AOI bbox."""
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="min_lon/min_lat must be less than max_lon/max_lat")
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    if lon_span > MAX_BBOX_SUMMARY_DEGREES or lat_span > MAX_BBOX_SUMMARY_DEGREES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"bbox too large ({lon_span:.4f} x {lat_span:.4f} degrees); max "
                f"{MAX_BBOX_SUMMARY_DEGREES} degrees (~10km) per side for this tool"
            ),
        )

    client = TomTomClient()
    try:
        raw = await client.get_incidents_for_bbox(min_lon, min_lat, max_lon, max_lat)
    finally:
        await client.aclose()

    incidents = normalize_incidents(raw)
    by_magnitude: dict[str, int] = {}
    for incident in incidents:
        magnitude = incident.get("magnitude_of_delay")
        label = MAGNITUDE_OF_DELAY_LABELS.get(magnitude, "unknown")
        by_magnitude[label] = by_magnitude.get(label, 0) + 1

    return {
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "incident_count": len(incidents),
        "by_magnitude_of_delay": by_magnitude,
    }
