from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import Alert
from app.db.session import get_db
from app.services.alert_service import approve_alert, send_alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/{alert_id}/approve")
def approve(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    user=Depends(require_role("operator")),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    try:
        alert = approve_alert(db, alert, approved_by=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"id": str(alert.id), "status": alert.status, "approved_by": alert.approved_by}


@router.post("/{alert_id}/send")
def send(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    try:
        alert = send_alert(db, alert)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"id": str(alert.id), "status": alert.status, "sent_at": alert.sent_at}
