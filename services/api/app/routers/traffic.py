"""Live traffic + history + manual ingestion trigger (spec section 11)."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import TrafficFlowObservation
from app.db.session import get_db
from app.schemas.traffic import FlowObservationOut, IngestionRunResult
from app.services.ingestion_service import run_ingestion_once

router = APIRouter(tags=["traffic"])


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
