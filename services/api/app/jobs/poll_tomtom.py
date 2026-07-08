"""Scheduled TomTom polling worker (spec sections 5, 6).

Run standalone:
    python -m app.jobs.poll_tomtom

Docker Compose runs this as the `worker` service (spec section 19/N:
`command: python -m app.jobs.poll_tomtom`).

Adaptive polling (spec section 5.3): this MVP scheduler runs a single fixed
base interval (every 2 minutes, matching "normal daytime") and polls every
active probe point on each tick -- it does NOT yet implement the full
per-probe adaptive backoff table (5-10 min at night, exponential backoff
after rate-limit errors). `probe_points.polling_interval_seconds` is stored
and exposed via the admin API for future use, but not yet consulted here.
This is a known simplification, called out in the README, not a hidden gap.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.ingestion_service import run_ingestion_once

logger = logging.getLogger(__name__)

BASE_POLL_INTERVAL_SECONDS = 120  # spec 5.3 "normal daytime"


def poll_job() -> None:
    db = SessionLocal()
    try:
        result = asyncio.run(run_ingestion_once(db))
        logger.info(
            "Ingestion run complete: probes=%s flow=%s incidents=%s anomalies=%s errors=%s",
            result.probe_points_polled,
            result.flow_observations_stored,
            result.incidents_upserted,
            result.anomalies_detected,
            len(result.errors),
        )
        for err in result.errors:
            logger.warning("Ingestion error: %s", err)
    finally:
        db.close()


def main() -> None:
    configure_logging(level=logging.INFO)
    logger.info("Starting TomTom polling worker (base interval=%ss)", BASE_POLL_INTERVAL_SECONDS)
    scheduler = BlockingScheduler()
    scheduler.add_job(poll_job, "interval", seconds=BASE_POLL_INTERVAL_SECONDS)
    # Run once immediately on startup (the "interval" trigger above only
    # fires its first run after one full interval has elapsed).
    poll_job()
    scheduler.start()


if __name__ == "__main__":
    main()
