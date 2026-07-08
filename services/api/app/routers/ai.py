"""AI endpoints (spec sections 11, 14): predictive alert, command center,
mitigation draft, citizen-report vision. Every endpoint here builds a
grounded DB-facts context first and only then calls Gemini -- Gemini is
never given free rein to answer from memory (spec section 10.1 rule)."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AIInsight, TrafficAnomaly
from app.db.session import get_db
from app.schemas.ai import (
    CommandAnswer,
    CommandQuery,
    EvidenceRow,
    MitigationDraftOut,
    MitigationDraftRequest,
)
from app.services.gemini_predictive_alert import GeminiPredictiveAlertService
from app.services.gemini_service import GeminiUnavailableError, answer_command_query, draft_mitigation

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/predictive-alert")
def predictive_alert(payload: dict):
    """Per spec section 14: backend should build this payload from database
    queries in production flows (see app/routers/sumo.py /summarize-with-gemini
    and the command center for examples of grounded-context building); this
    route accepts a pre-built payload matching PredictiveAlertInput."""
    try:
        service = GeminiPredictiveAlertService()
        result = service.generate_alert(payload)
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _classify_intent(question: str) -> str:
    """Minimal keyword-based intent classifier (spec section 10.1 step 2).
    Good enough for the MVP command set; swap for a real classifier later."""
    q = question.lower()
    if "summariz" in q or "summary" in q:
        return "summarize_period"
    if "repeated" in q or "bottleneck" in q:
        return "repeated_bottlenecks"
    if "advisory" in q or "draft" in q:
        return "draft_advisory"
    if "police" in q or "deploy" in q:
        return "police_deployment_focus"
    return "current_cause_of_delay"


@router.post("/command", response_model=CommandAnswer)
def ai_command(payload: CommandQuery, db: Session = Depends(get_db)) -> CommandAnswer:
    intent = _classify_intent(payload.question)

    # Step 3: run SQL/PostGIS query -- grounded context comes ONLY from here.
    open_anomalies = list(
        db.scalars(
            select(TrafficAnomaly)
            .where(TrafficAnomaly.status.in_(["open", "acknowledged"]))
            .order_by(TrafficAnomaly.detected_at.desc())
            .limit(20)
        )
    )
    context = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "open_anomaly_count": len(open_anomalies),
        "open_anomalies": [
            {
                "id": str(a.id),
                "severity": a.severity,
                "detected_at": a.detected_at.isoformat(),
                "observed_speed_kmph": a.observed_speed_kmph,
                "baseline_speed_kmph": a.baseline_speed_kmph,
                "delay_sec": a.delay_sec,
                "probe_point_id": str(a.probe_point_id) if a.probe_point_id else None,
            }
            for a in open_anomalies
        ],
    }

    try:
        result = answer_command_query(payload.question, context, intent)
    except GeminiUnavailableError:
        # Graceful degradation: still return a grounded (if unpolished)
        # answer built purely from DB facts, per the "never fake data" rule.
        return CommandAnswer(
            intent=intent,
            answer=(
                f"Gemini is not configured. There are currently {len(open_anomalies)} open "
                "traffic anomalies in the database. Configure GEMINI_API_KEY for a "
                "natural-language explanation."
            ),
            evidence=[
                EvidenceRow(label="open_anomaly_count", value=str(len(open_anomalies)), source="db")
            ],
            confidence=0.3,
            missing_data=["Gemini API key not configured"],
        )

    insight = AIInsight(
        insight_type="command_center",
        model_name=get_settings().gemini_model,
        prompt_version="v1",
        input_payload=context,
        output_payload=result.model_dump(),
        confidence=result.confidence,
        human_review_status="pending",
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    return CommandAnswer(
        intent=result.intent,
        answer=result.answer,
        evidence=[
            EvidenceRow(label="open_anomaly_count", value=str(len(open_anomalies)), source="db")
        ],
        confidence=result.confidence,
        assumptions=result.assumptions,
        missing_data=result.missing_data,
        suggested_advisory=result.suggested_advisory,
        ai_insight_id=insight.id,
    )


@router.post("/mitigation-draft", response_model=MitigationDraftOut)
def ai_mitigation_draft(payload: MitigationDraftRequest, db: Session = Depends(get_db)) -> MitigationDraftOut:
    anomaly = db.get(TrafficAnomaly, payload.anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    try:
        result = draft_mitigation(anomaly.evidence)
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    insight = AIInsight(
        aoi_id=anomaly.aoi_id,
        anomaly_id=anomaly.id,
        insight_type="mitigation_draft",
        model_name=get_settings().gemini_model,
        prompt_version="v1",
        input_payload=anomaly.evidence,
        output_payload=result.model_dump(),
        confidence=result.confidence,
        human_review_status="pending",
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    return MitigationDraftOut(
        ai_insight_id=insight.id,
        problem_summary=result.problem_summary,
        likely_root_cause=result.likely_root_cause,
        impacted_locations=result.impacted_locations,
        police_deployment=result.police_deployment,
        citizen_advisory_draft=result.citizen_advisory_draft,
        suggested_reroutes=result.suggested_reroutes,
        signal_timing_note=result.signal_timing_note,
        escalation_priority=result.escalation_priority,
        confidence=result.confidence,
        requires_human_approval=True,
    )
