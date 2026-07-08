"""Daily report generation job (spec section 17).

Run standalone (e.g. from cron or Cloud Scheduler later):
    python -m app.jobs.daily_report [--date YYYY-MM-DD]

Generates yesterday's report by default and logs a summary. The report
itself is always computed on-demand from stored data by
app/services/report_service.py -- this job is a convenience wrapper, not a
separate storage path.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.report_service import generate_daily_report

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD, defaults to yesterday (UTC)")
    args = parser.parse_args()

    target_date = (
        dt.date.fromisoformat(args.date)
        if args.date
        else (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).date()
    )

    db = SessionLocal()
    try:
        report = generate_daily_report(db, target_date)
        logger.info("Daily report for %s: %s total anomalies", target_date, report["total_anomalies"])
        print(json.dumps(report, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
