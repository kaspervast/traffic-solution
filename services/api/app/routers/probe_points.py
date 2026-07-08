"""Probe point CRUD (spec sections 5.2, 11)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import AreaOfInterest, ProbePoint
from app.db.session import get_db
from app.schemas.traffic import ProbePointCreate, ProbePointOut, ProbePointUpdate

router = APIRouter(prefix="/api/probe-points", tags=["probe-points"])


def _to_out(p: ProbePoint) -> ProbePointOut:
    point = to_shape(p.geom)
    return ProbePointOut(
        id=p.id,
        name=p.name,
        lat=point.y,
        lon=point.x,
        priority=p.priority,
        polling_interval_seconds=p.polling_interval_seconds,
        is_active=p.is_active,
        notes=p.notes,
        road_segment_id=p.road_segment_id,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=list[ProbePointOut])
def list_probe_points(active_only: bool = False, db: Session = Depends(get_db)) -> list[ProbePointOut]:
    stmt = select(ProbePoint)
    if active_only:
        stmt = stmt.where(ProbePoint.is_active.is_(True))
    stmt = stmt.order_by(ProbePoint.priority, ProbePoint.name)
    return [_to_out(p) for p in db.scalars(stmt)]


@router.post("", response_model=ProbePointOut, status_code=201)
def create_probe_point(
    payload: ProbePointCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
) -> ProbePointOut:
    aoi = db.scalar(select(AreaOfInterest).order_by(AreaOfInterest.created_at.desc()).limit(1))
    probe = ProbePoint(
        aoi_id=aoi.id if aoi else None,
        name=payload.name,
        priority=payload.priority,
        geom=WKTElement(f"POINT({payload.lon} {payload.lat})", srid=4326),
        polling_interval_seconds=payload.polling_interval_seconds,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    db.add(probe)
    db.commit()
    db.refresh(probe)
    return _to_out(probe)


@router.patch("/{probe_id}", response_model=ProbePointOut)
def update_probe_point(
    probe_id: uuid.UUID,
    payload: ProbePointUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
) -> ProbePointOut:
    probe = db.get(ProbePoint, probe_id)
    if probe is None:
        raise HTTPException(status_code=404, detail="Probe point not found")

    data = payload.model_dump(exclude_unset=True)
    if "lat" in data or "lon" in data:
        current = to_shape(probe.geom)
        lat = data.pop("lat", current.y)
        lon = data.pop("lon", current.x)
        probe.geom = WKTElement(f"POINT({lon} {lat})", srid=4326)
    for field, value in data.items():
        setattr(probe, field, value)

    db.commit()
    db.refresh(probe)
    return _to_out(probe)


@router.delete("/{probe_id}", status_code=204)
def delete_probe_point(
    probe_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_role("admin")),
) -> None:
    probe = db.get(ProbePoint, probe_id)
    if probe is None:
        raise HTTPException(status_code=404, detail="Probe point not found")
    db.delete(probe)
    db.commit()
