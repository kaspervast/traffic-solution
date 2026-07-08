"""Alert approval workflow (spec sections 12.2, 16, 18).

Alerts are always created as drafts. Nothing in this module ever
auto-sends: `approve_alert` only flips status to 'approved' with an
approving operator recorded; `send_alert` is a separate explicit step that
only proceeds if status is already 'approved'.
"""

from __future__ import annotations

import datetime as dt
import logging
import smtplib
import uuid
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Alert

logger = logging.getLogger(__name__)


def create_draft_alert(
    db: Session,
    *,
    aoi_id: uuid.UUID | None,
    anomaly_id: uuid.UUID | None,
    ai_insight_id: uuid.UUID | None,
    title: str,
    message: str,
    severity: str,
) -> Alert:
    alert = Alert(
        aoi_id=aoi_id,
        anomaly_id=anomaly_id,
        ai_insight_id=ai_insight_id,
        title=title,
        message=message,
        severity=severity,
        status="draft",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def approve_alert(db: Session, alert: Alert, approved_by: str) -> Alert:
    if alert.status != "draft":
        raise ValueError(f"Only draft alerts can be approved (current status: {alert.status})")
    alert.status = "approved"
    alert.approved_at = dt.datetime.now(dt.timezone.utc)
    alert.approved_by = approved_by
    db.commit()
    db.refresh(alert)
    return alert


def send_alert(db: Session, alert: Alert) -> Alert:
    """Sends an already-approved alert via email (spec section 16: email
    first, MVP channel). Never called for a non-approved alert -- this is
    the hard 'draft-first, human-approved' gate from spec sections 16/23/W."""
    if alert.status != "approved":
        raise ValueError(f"Only approved alerts can be sent (current status: {alert.status})")

    settings = get_settings()
    if not settings.email_smtp_host:
        alert.status = "failed"
        db.commit()
        raise RuntimeError("EMAIL_SMTP_HOST not configured -- cannot send alert")

    try:
        msg = EmailMessage()
        msg["Subject"] = alert.title
        msg["From"] = settings.email_smtp_user or "traffic-alerts@localhost"
        msg["To"] = settings.email_smtp_user or "traffic-alerts@localhost"
        msg.set_content(alert.message)

        with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.email_smtp_user and settings.email_smtp_password:
                smtp.login(settings.email_smtp_user, settings.email_smtp_password)
            smtp.send_message(msg)

        alert.status = "sent"
        alert.sent_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
        db.refresh(alert)
        return alert
    except Exception:
        logger.exception("Failed to send alert %s", alert.id)
        alert.status = "failed"
        db.commit()
        raise
