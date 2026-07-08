"""Gemini command center / mitigation draft / scenario authoring / result
summary service (spec sections 10.1, 10.3, S).

Hard rule enforced throughout this module: Gemini never invents numeric
traffic metrics, road names, or events. The backend always retrieves DB
facts first and passes only that grounded context into the prompt; Gemini's
job is explanation, drafting, and summarization -- never data generation.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal

from google import genai
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import get_settings
from app.schemas.sumo import SumoScenarioRequest

logger = logging.getLogger(__name__)


class GeminiUnavailableError(RuntimeError):
    """Raised when GEMINI_API_KEY is not configured. Callers should degrade
    gracefully (e.g. command center falls back to a template answer built
    purely from DB facts) rather than 500 the whole request."""


def _client() -> tuple[genai.Client, str]:
    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key == "replace_me":
        raise GeminiUnavailableError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.gemini_api_key), settings.gemini_model


def _retry_call(fn):
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type(Exception),
    )(fn)


COMMAND_CENTER_SYSTEM_INSTRUCTION = """
You are an AI assistant for a city traffic command center in Rajkot, India.
Answer ONLY using the facts provided in the grounded context JSON. Do not
use outside knowledge about Rajkot or any city. Do not invent road names,
speeds, delays, incident counts, or any other number. If the context does
not contain enough information to answer confidently, say so explicitly and
lower your confidence score. Every claim in your answer must be traceable
to a row in the evidence you were given. Always note that any suggested
police deployment, signal change, or citizen advisory requires human
approval before use.
""".strip()


class GroundedCommandResult(BaseModel):
    intent: str
    answer: str
    confidence: float
    assumptions: list[str] = []
    missing_data: list[str] = []
    suggested_advisory: str | None = None


def answer_command_query(question: str, context: dict[str, Any], intent: str) -> GroundedCommandResult:
    """Stage: grounded command-center answer (spec section 10.1). `context`
    must already be built from DB queries by the caller -- this function
    never queries the DB itself."""
    client, model = _client()
    prompt = f"""
Operator question: {question}

Classified intent: {intent}

Grounded context (the ONLY facts you may use):
{json.dumps(context, indent=2, default=str)}

Respond with JSON: {{"intent": str, "answer": str, "confidence": float 0-1,
"assumptions": [str], "missing_data": [str], "suggested_advisory": str|null}}
""".strip()

    @_retry_call
    def _call():
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "system_instruction": COMMAND_CENTER_SYSTEM_INSTRUCTION,
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_json_schema": GroundedCommandResult.model_json_schema(),
            },
        )

    response = _call()
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return GroundedCommandResult.model_validate(json.loads(response.text))


MITIGATION_SYSTEM_INSTRUCTION = """
You are an AI traffic operations analyst. Draft an incident mitigation plan
using ONLY the anomaly evidence JSON provided. Never invent road names,
police unit names, or numbers not present in the evidence. All actions are
drafts requiring human approval -- never phrase anything as already
executed or auto-authorized.
""".strip()


class MitigationDraftResult(BaseModel):
    problem_summary: str
    likely_root_cause: str
    impacted_locations: list[str]
    police_deployment: list[str]
    citizen_advisory_draft: str
    suggested_reroutes: list[str]
    signal_timing_note: str | None
    escalation_priority: Literal["low", "medium", "high", "urgent"]
    confidence: float


def draft_mitigation(anomaly_evidence: dict[str, Any]) -> MitigationDraftResult:
    client, model = _client()
    prompt = f"""
Anomaly evidence JSON:
{json.dumps(anomaly_evidence, indent=2, default=str)}

Draft a mitigation plan as JSON matching the required schema.
""".strip()

    @_retry_call
    def _call():
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "system_instruction": MITIGATION_SYSTEM_INSTRUCTION,
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_json_schema": MitigationDraftResult.model_json_schema(),
            },
        )

    response = _call()
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return MitigationDraftResult.model_validate(json.loads(response.text))


# ---------------------------------------------------------------------------
# Gemini + SUMO two-stage flow (spec section S)
# ---------------------------------------------------------------------------

SCENARIO_AUTHORING_SYSTEM_INSTRUCTION = """
You are drafting a SUMO traffic simulation scenario configuration for a city
traffic engineer to review. You may ONLY reference the SUMO edge ID(s),
current TomTom speed/delay context, and incidents supplied in the context
JSON -- never invent edge IDs or traffic-light IDs that are not listed.
Output strictly valid JSON matching the SumoScenarioRequest schema. This is
a DRAFT only; a human must review and approve it before it is executed.
""".strip()


def draft_scenario_request(
    user_request_text: str, context: dict[str, Any], aoi_id: str, network_id: str
) -> SumoScenarioRequest:
    """Stage 1: scenario authoring (spec section S). `context` must include
    the selected SUMO edge id(s), current TomTom speed/delay for the mapped
    road segment, and recent anomalies/incidents -- all pulled from the DB
    by the caller before this function is invoked."""
    client, model = _client()
    prompt = f"""
User request: {user_request_text}

Context (only facts you may reference):
{json.dumps(context, indent=2, default=str)}

aoi_id: {aoi_id}
network_id: {network_id}

Return a SumoScenarioRequest JSON object.
""".strip()

    @_retry_call
    def _call():
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "system_instruction": SCENARIO_AUTHORING_SYSTEM_INSTRUCTION,
                "temperature": 0.1,
                "response_mime_type": "application/json",
                "response_json_schema": SumoScenarioRequest.model_json_schema(),
            },
        )

    response = _call()
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    try:
        return SumoScenarioRequest.model_validate(json.loads(response.text))
    except ValidationError as exc:
        logger.error("Gemini scenario draft failed strict validation: %s", response.text)
        raise ValueError(f"Gemini scenario draft failed validation: {exc}") from exc


RESULT_SUMMARY_SYSTEM_INSTRUCTION = """
You are summarizing SUMO simulation comparison results (baseline vs
scenario) for a city traffic engineer. Use ONLY the metrics JSON provided.
Never invent travel time, speed, or queue numbers not present in the
metrics. Clearly state this is a planning-level simulation estimate that
requires field/engineering validation before any operational change, and
that it depends on OSM network quality and synthetic/calibrated demand.
""".strip()


class ScenarioResultSummary(BaseModel):
    summary: str
    key_findings: list[str]
    limitations: list[str]
    recommended_next_actions: list[str]
    confidence: float


def summarize_scenario_result(comparison_metrics: dict[str, Any]) -> ScenarioResultSummary:
    """Stage 2: result summarization (spec section S). Only runs after real
    SUMO metrics exist in `comparison_metrics` -- never before."""
    client, model = _client()
    prompt = f"""
SUMO baseline-vs-scenario comparison metrics JSON:
{json.dumps(comparison_metrics, indent=2, default=str)}

Summarize as JSON matching the required schema.
""".strip()

    @_retry_call
    def _call():
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "system_instruction": RESULT_SUMMARY_SYSTEM_INSTRUCTION,
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_json_schema": ScenarioResultSummary.model_json_schema(),
            },
        )

    response = _call()
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return ScenarioResultSummary.model_validate(json.loads(response.text))
