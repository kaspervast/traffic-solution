from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import TrafficAnomaly
from app.db.session import get_db
from app.schemas.traffic import AnomalyOut, AnomalyStatusUpdate

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


def _to_out(a: TrafficAnomaly) -> AnomalyOut:
    return AnomalyOut(
        id=a.id,
        probe_point_id=a.probe_point_id,
        road_segment_id=a.road_segment_id,
        detected_at=a.detected_at,
        anomaly_type=a.anomaly_type,
        severity=a.severity,
        score=a.score,
        baseline_speed_kmph=a.baseline_speed_kmph,
        observed_speed_kmph=a.observed_speed_kmph,
        delay_sec=a.delay_sec,
        evidence=a.evidence,
        status=a.status,
    )


@router.get("/open", response_model=list[AnomalyOut])
def anomalies_open(severity: str | None = None, db: Session = Depends(get_db)) -> list[AnomalyOut]:
    stmt = select(TrafficAnomaly).where(TrafficAnomaly.status.in_(["open", "acknowledged"]))
    if severity:
        stmt = stmt.where(TrafficAnomaly.severity == severity)
    stmt = stmt.order_by(TrafficAnomaly.detected_at.desc()).limit(500)
    return [_to_out(a) for a in db.scalars(stmt)]


@router.patch("/{anomaly_id}/status", response_model=AnomalyOut)
def update_anomaly_status(
    anomaly_id: uuid.UUID,
    payload: AnomalyStatusUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
) -> AnomalyOut:
    anomaly = db.get(TrafficAnomaly, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    anomaly.status = payload.status
    db.commit()
    db.refresh(anomaly)
    return _to_out(anomaly)
