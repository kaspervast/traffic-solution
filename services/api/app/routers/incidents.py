from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TrafficIncident
from app.db.session import get_db
from app.schemas.traffic import IncidentOut

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/live", response_model=list[IncidentOut])
def incidents_live(db: Session = Depends(get_db)) -> list[IncidentOut]:
    stmt = (
        select(TrafficIncident)
        .where(TrafficIncident.is_active.is_(True))
        .order_by(TrafficIncident.last_seen_at.desc())
    )
    return [
        IncidentOut(
            id=i.id,
            provider_incident_id=i.provider_incident_id,
            category=i.category,
            icon_category=i.icon_category,
            magnitude_of_delay=i.magnitude_of_delay,
            from_text=i.from_text,
            to_text=i.to_text,
            description=i.description,
            delay_sec=i.delay_sec,
            length_m=i.length_m,
            start_time=i.start_time,
            end_time=i.end_time,
            is_active=i.is_active,
            last_seen_at=i.last_seen_at,
        )
        for i in db.scalars(stmt)
    ]
