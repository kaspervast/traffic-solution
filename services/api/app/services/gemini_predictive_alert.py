"""
Gemini predictive traffic alert service.

Install:
    pip install google-genai pydantic tenacity

Environment:
    export GEMINI_API_KEY="your_key"
    export GEMINI_MODEL="gemini-3.5-flash"

Purpose:
    Takes normalized traffic anomalies, weather, and local events.
    Returns a structured predictive alert and mitigation strategy.

This is the spec's (section 13) production-ready base script, kept
verbatim except for two changes needed to actually run in this repo:
  1. api_key/model default to app.core.config.get_settings() instead of
     bare os.getenv(), so it picks up the repo-root .env the same way the
     rest of the API does.
  2. datetime.utcnow() (deprecated in newer Python) -> datetime.now(UTC) in
     the __main__ demo block only; the class/schema code is untouched.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

from google import genai
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

logger = logging.getLogger(__name__)


Severity = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class TrafficAnomaly(BaseModel):
    anomaly_id: str | None = None
    road_name: str | None = None
    probe_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    detected_at: datetime
    anomaly_type: str
    severity: Severity
    current_speed_kmph: float | None = None
    free_flow_speed_kmph: float | None = None
    speed_ratio: float | None = None
    delay_sec: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    nearby_incidents: list[dict[str, Any]] = Field(default_factory=list)


class WeatherSnapshot(BaseModel):
    observed_at: datetime
    condition_text: str | None = None
    temperature_c: float | None = None
    rainfall_mm: float | None = None
    humidity_percent: float | None = None
    wind_speed_kmph: float | None = None
    visibility_m: float | None = None


class LocalEvent(BaseModel):
    title: str
    venue: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    expected_crowd: int | None = None
    distance_from_anomaly_m: float | None = None
    event_type: str | None = None


class PredictiveAlertInput(BaseModel):
    generated_at: datetime
    aoi_name: str = "Rajkot 1 km pilot zone"
    center_lat: float = 22.329077
    center_lon: float = 70.769564
    forecast_horizon_minutes: int = Field(default=120, ge=15, le=360)
    anomalies: list[TrafficAnomaly]
    weather: WeatherSnapshot | None = None
    local_events: list[LocalEvent] = Field(default_factory=list)
    operator_notes: str | None = None


class MitigationAction(BaseModel):
    action_type: Literal[
        "police_deployment",
        "citizen_advisory",
        "reroute_suggestion",
        "signal_timing_review",
        "field_verification",
        "monitor_only",
        "other",
    ]
    priority: Literal["low", "medium", "high", "urgent"]
    action: str
    location_hint: str | None = None
    reason: str
    requires_human_approval: bool = True


class PredictiveAlertOutput(BaseModel):
    alert_title: str
    risk_level: RiskLevel
    forecast_window: str
    predicted_impact_summary: str
    likely_root_causes: list[str]
    affected_locations: list[str]
    evidence: list[str]
    mitigation_actions: list[MitigationAction]
    citizen_message_draft: str
    police_control_room_summary: str
    confidence_score: float = Field(ge=0, le=1)
    assumptions: list[str]
    missing_data: list[str]
    human_review_required: bool = True


SYSTEM_INSTRUCTION = """
You are an AI traffic operations analyst for a city traffic command center.
You must produce operationally useful but conservative recommendations.
Use only the provided JSON facts. Do not invent incidents, road names, weather, events, or official actions.
Signal timing, route diversion, police deployment, and public advisories are recommendations only and require human approval.
If evidence is weak, lower the confidence score and list missing data.
Return valid JSON matching the required schema.
""".strip()


class GeminiPredictiveAlertService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        if api_key is None or model is None:
            try:
                from app.core.config import get_settings

                settings = get_settings()
                api_key = api_key or settings.gemini_api_key
                model = model or settings.gemini_model
            except Exception:  # pragma: no cover - fallback if app.core unavailable
                pass

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key or self.api_key == "replace_me":
            raise RuntimeError("GEMINI_API_KEY is not set")

        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.client = genai.Client(api_key=self.api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def generate_alert(self, payload: dict[str, Any]) -> PredictiveAlertOutput:
        try:
            validated_input = PredictiveAlertInput.model_validate(payload)
        except ValidationError as exc:
            logger.exception("Invalid predictive alert input")
            raise ValueError(f"Invalid predictive alert input: {exc}") from exc

        prompt = self._build_prompt(validated_input)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_json_schema": PredictiveAlertOutput.model_json_schema(),
            },
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response")

        try:
            parsed = json.loads(response.text)
            return PredictiveAlertOutput.model_validate(parsed)
        except Exception as exc:
            logger.error("Raw Gemini response: %s", response.text)
            raise RuntimeError("Failed to parse Gemini structured output") from exc

    def _build_prompt(self, data: PredictiveAlertInput) -> str:
        compact_json = data.model_dump_json(indent=2)
        return f"""
Analyze the following live traffic operations packet for the Rajkot 1 km pilot zone.

Tasks:
1. Predict congestion risk for the next {data.forecast_horizon_minutes} minutes.
2. Identify likely root causes using only supplied anomalies, incidents, weather, and events.
3. Draft mitigation actions suitable for traffic police/city officials.
4. Draft a short citizen advisory.
5. State confidence, assumptions, and missing data.

Input JSON:
{compact_json}
""".strip()


if __name__ == "__main__":
    sample_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast_horizon_minutes": 120,
        "anomalies": [
            {
                "anomaly_id": "demo-001",
                "road_name": "Unknown road segment - probe A",
                "probe_name": "Probe A",
                "lat": 22.329077,
                "lon": 70.769564,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "anomaly_type": "slowdown",
                "severity": "high",
                "current_speed_kmph": 12.0,
                "free_flow_speed_kmph": 42.0,
                "speed_ratio": 0.28,
                "delay_sec": 420,
                "confidence": 0.88,
                "nearby_incidents": [],
            }
        ],
        "weather": {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "condition_text": "clear",
            "temperature_c": 31.0,
            "rainfall_mm": 0.0,
            "humidity_percent": 50,
            "wind_speed_kmph": 8,
        },
        "local_events": [],
        "operator_notes": "Demo run. Road name not yet verified.",
    }

    service = GeminiPredictiveAlertService()
    alert = service.generate_alert(sample_payload)
    print(alert.model_dump_json(indent=2))
