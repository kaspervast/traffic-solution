from __future__ import annotations

import csv
import datetime as dt
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.report_service import generate_daily_report, generate_weekly_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily")
def daily_report(date: dt.date, db: Session = Depends(get_db)):
    return generate_daily_report(db, date)


@router.get("/daily.csv")
def daily_report_csv(date: dt.date, db: Session = Depends(get_db)):
    report = generate_daily_report(db, date)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value"])
    writer.writerow(["date", report["date"]])
    writer.writerow(["total_anomalies", report["total_anomalies"]])
    for sev, count in report["severity_counts"].items():
        writer.writerow([f"severity_{sev}", count])
    writer.writerow([])
    writer.writerow(["probe_point_name", "anomaly_count", "avg_speed_ratio", "max_delay_sec"])
    for loc in report["worst_locations"]:
        writer.writerow(
            [loc["probe_point_name"], loc["anomaly_count"], loc["avg_speed_ratio"], loc["max_delay_sec"]]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=daily_report_{date}.csv"},
    )


@router.get("/weekly")
def weekly_report(week_start: dt.date, db: Session = Depends(get_db)):
    return generate_weekly_report(db, week_start)
