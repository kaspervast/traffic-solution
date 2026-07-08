"""Weather client (spec section 5.4). Uses Open-Meteo -- no API key required,
which keeps the MVP's "external data sources" list runnable with zero extra
signup. Swap the base URL / add auth if the deployment prefers OpenWeather
or an IMD source instead; the normalized output shape stays the same."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherClient:
    def __init__(self, base_url: str = OPEN_METEO_URL) -> None:
        self.base_url = base_url

    async def get_current_weather(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,visibility",
            "timezone": "auto",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()


def normalize_weather(raw: dict[str, Any]) -> dict[str, Any]:
    current = raw.get("current", {}) or {}
    return {
        "temperature_c": current.get("temperature_2m"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "rainfall_mm": current.get("precipitation"),
        "wind_speed_kmph": current.get("wind_speed_10m"),
        "visibility_m": current.get("visibility"),
        "condition_text": None,  # Open-Meteo "current" block has no text condition without weathercode mapping
        "observed_at": current.get("time"),
        "raw": raw,
    }
