"""Rajkot AI Traffic Command Center - FastAPI backend entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.routers import ai, alerts, anomalies, aoi, health, incidents, probe_points, reports, sumo, traffic

configure_logging(level=logging.INFO)

app = FastAPI(
    title="Rajkot AI Traffic Command Center API",
    description=(
        "1 km pilot-zone traffic intelligence platform. TomTom = live "
        "observation, SUMO = simulation/what-if planning, Gemini = "
        "explanation/drafting only. See /health."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(aoi.router)
app.include_router(probe_points.router)
app.include_router(traffic.router)
app.include_router(incidents.router)
app.include_router(anomalies.router)
app.include_router(ai.router)
app.include_router(sumo.router)
app.include_router(reports.router)
app.include_router(alerts.router)
