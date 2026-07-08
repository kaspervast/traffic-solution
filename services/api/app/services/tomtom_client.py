"""TomTom API client (spec sections 4, 15).

- async httpx.AsyncClient
- retry/backoff with jitter via tenacity
- timeout
- request logging without exposing the API key
- normalized response models + raw response preservation
- basic rate-limit (429) handling
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TomTomRateLimitError(Exception):
    """Raised on HTTP 429. Callers should back off further than the client's
    own internal retries already did."""


class TomTomAPIError(Exception):
    pass


def _redact_url(url: str) -> str:
    """Never log the raw API key -- used only for log lines, never for the
    actual request."""
    if "key=" not in url:
        return url
    head, _, tail = url.partition("key=")
    rest = tail.split("&", 1)
    remainder = f"&{rest[1]}" if len(rest) > 1 else ""
    return f"{head}key=***REDACTED***{remainder}"


class TomTomClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.tomtom_api_key
        self.base_url = (base_url or settings.tomtom_base_url).rstrip("/")
        self.flow_zoom = settings.tomtom_flow_zoom
        self.flow_style = settings.tomtom_flow_style
        self.flow_unit = settings.tomtom_flow_unit
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "TomTomClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=15),
        retry=retry_if_exception_type((httpx.TransportError, TomTomRateLimitError)),
    )
    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        logger.info("TomTom GET %s params=%s", _redact_url(url), {k: v for k, v in params.items() if k != "key"})
        response = await self._client.get(url, params=params)
        if response.status_code == 429:
            logger.warning("TomTom rate limit hit (429) for %s", _redact_url(str(response.url)))
            raise TomTomRateLimitError(f"Rate limited: {_redact_url(str(response.url))}")
        if response.status_code >= 400:
            body_preview = response.text[:300]
            raise TomTomAPIError(f"TomTom API error {response.status_code}: {body_preview}")
        return response.json()

    # -- Traffic Flow Segment Data v4 (spec 4.1.A) --------------------------

    async def get_flow_segment(self, lat: float, lon: float) -> dict[str, Any]:
        url = f"{self.base_url}/traffic/services/4/flowSegmentData/{self.flow_style}/{self.flow_zoom}/json"
        params = {
            "key": self.api_key,
            "point": f"{lat},{lon}",
            "unit": self.flow_unit,
            "openLr": "false",
        }
        raw = await self._get(url, params)
        return raw

    # -- Traffic Incident Details v5 (spec 4.1.B) ----------------------------

    async def get_incidents_for_bbox(
        self, min_lon: float, min_lat: float, max_lon: float, max_lat: float
    ) -> dict[str, Any]:
        url = f"{self.base_url}/traffic/services/5/incidentDetails"
        fields = (
            "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,"
            "magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,"
            "from,to,length,delay,roadNumbers,timeValidity,probabilityOfOccurrence,"
            "numberOfReports,lastReportTime}}}"
        )
        params = {
            "key": self.api_key,
            "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
            "fields": fields,
            "language": "en-GB",
            "timeValidityFilter": "present,future",
        }
        raw = await self._get(url, params)
        return raw


# ---------------------------------------------------------------------------
# Normalization (spec section 15)
# ---------------------------------------------------------------------------


def normalize_flow_segment(raw: dict[str, Any]) -> dict[str, Any]:
    """Converts a raw TomTom flowSegmentData response into internal fields.
    Never fabricates values: any field TomTom omits stays None."""
    flow = raw.get("flowSegmentData", {}) or {}
    current_speed = flow.get("currentSpeed")
    free_flow_speed = flow.get("freeFlowSpeed")
    current_tt = flow.get("currentTravelTime")
    free_flow_tt = flow.get("freeFlowTravelTime")

    speed_ratio = None
    if current_speed is not None and free_flow_speed:
        speed_ratio = current_speed / free_flow_speed if free_flow_speed > 0 else None

    delay_sec = None
    if current_tt is not None and free_flow_tt is not None:
        delay_sec = current_tt - free_flow_tt

    return {
        "current_speed_kmph": current_speed,
        "free_flow_speed_kmph": free_flow_speed,
        "current_travel_time_sec": current_tt,
        "free_flow_travel_time_sec": free_flow_tt,
        "confidence": flow.get("confidence"),
        "road_closure": flow.get("roadClosure", False),
        "coordinates": flow.get("coordinates", {}).get("coordinate", []),
        "speed_ratio": speed_ratio,
        "delay_sec": delay_sec,
        "raw": raw,
    }


def normalize_incidents(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Converts a raw TomTom incidentDetails response into a list of
    normalized incident dicts, one per feature. Road names/text fields are
    left as None (never fabricated) when TomTom does not supply them."""
    normalized: list[dict[str, Any]] = []
    for feature in raw.get("incidents", []) or []:
        props = feature.get("properties", {}) or {}
        events = props.get("events", []) or []
        description = events[0].get("description") if events else None
        normalized.append(
            {
                "provider_incident_id": str(props.get("id")),
                "category": (events[0].get("iconCategory") if events else props.get("iconCategory")),
                "icon_category": props.get("iconCategory"),
                "magnitude_of_delay": props.get("magnitudeOfDelay"),
                "probability_of_occurrence": props.get("probabilityOfOccurrence"),
                "number_of_reports": props.get("numberOfReports"),
                "from_text": props.get("from"),
                "to_text": props.get("to"),
                "road_numbers": props.get("roadNumbers") or [],
                "length_m": props.get("length"),
                "delay_sec": props.get("delay"),
                "description": description,
                "start_time": props.get("startTime"),
                "end_time": props.get("endTime"),
                "time_validity": props.get("timeValidity"),
                "geometry": feature.get("geometry"),
                "raw": feature,
            }
        )
    return normalized
