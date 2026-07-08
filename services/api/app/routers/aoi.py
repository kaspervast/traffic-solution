from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AreaOfInterest
from app.db.session import get_db
from app.schemas.traffic import AOIOut

router = APIRouter(prefix="/api/aoi", tags=["aoi"])


@router.get("/current", response_model=AOIOut)
def get_current_aoi(db: Session = Depends(get_db)) -> AOIOut:
    aoi = db.scalar(select(AreaOfInterest).order_by(AreaOfInterest.created_at.desc()).limit(1))
    if aoi is None:
        raise HTTPException(
            status_code=404,
            detail="No AOI seeded yet. Run scripts/seed_aoi.py first.",
        )
    center_point = to_shape(aoi.center)
    return AOIOut(
        id=aoi.id,
        name=aoi.name,
        radius_m=aoi.radius_m,
        bbox_min_lat=aoi.bbox_min_lat,
        bbox_min_lon=aoi.bbox_min_lon,
        bbox_max_lat=aoi.bbox_max_lat,
        bbox_max_lon=aoi.bbox_max_lon,
        center_lat=center_point.y,
        center_lon=center_point.x,
        created_at=aoi.created_at,
    )
