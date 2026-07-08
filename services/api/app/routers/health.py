from __future__ import annotations

import datetime as dt

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "rajkot-traffic-api",
        "time": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
