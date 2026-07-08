"""Parses SUMO run output files (tripinfo.xml, summary.xml, edgeData.xml)
into the metric shapes stored in `sumo_run_metrics` / `sumo_edge_metrics`
(spec section K).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_tripinfo(tripinfo_path: str | Path) -> dict[str, Any]:
    """Per-trip aggregate metrics: arrivals, average duration/waiting/time-loss."""
    path = Path(tripinfo_path)
    metrics: dict[str, Any] = {
        "total_arrived": 0,
        "average_travel_time_sec": None,
        "average_waiting_time_sec": None,
        "average_time_loss_sec": None,
        "total_time_loss_sec": 0.0,
        "average_speed_mps": None,
        "total_teleports": 0,
    }
    if not path.exists():
        return metrics

    durations, waits, losses, speeds = [], [], [], []
    for _, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "tripinfo":
            metrics["total_arrived"] += 1
            duration = float(elem.attrib.get("duration", 0))
            wait = float(elem.attrib.get("waitingTime", 0))
            loss = float(elem.attrib.get("timeLoss", 0))
            route_length = float(elem.attrib.get("routeLength", 0))
            durations.append(duration)
            waits.append(wait)
            losses.append(loss)
            if duration > 0:
                speeds.append(route_length / duration)
            elem.clear()

    if durations:
        metrics["average_travel_time_sec"] = sum(durations) / len(durations)
        metrics["average_waiting_time_sec"] = sum(waits) / len(waits)
        metrics["average_time_loss_sec"] = sum(losses) / len(losses)
        metrics["total_time_loss_sec"] = sum(losses)
    if speeds:
        metrics["average_speed_mps"] = sum(speeds) / len(speeds)
    return metrics


def parse_summary(summary_path: str | Path) -> dict[str, Any]:
    """Reads SUMO's <summary-output>: per-step loaded/inserted/running/
    ended/arrived counts and teleport totals. Returns totals at the final
    timestep plus the max concurrent teleport count seen."""
    path = Path(summary_path)
    out: dict[str, Any] = {
        "total_departed": None,
        "total_loaded": None,
        "total_teleports": 0,
    }
    if not path.exists():
        return out

    last_step = None
    max_teleports = 0
    for _, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "step":
            last_step = elem.attrib
            teleports = int(float(elem.attrib.get("teleports", 0)))
            max_teleports = max(max_teleports, teleports)
    if last_step:
        out["total_departed"] = int(float(last_step.get("inserted", 0)))
        out["total_loaded"] = int(float(last_step.get("loaded", 0)))
        out["total_teleports"] = max_teleports
    return out


def parse_edge_data(edge_data_path: str | Path) -> list[dict[str, Any]]:
    """Reads <edgeData> intervals -> per-edge speed/occupancy/waiting time.
    One row per (edge, interval)."""
    path = Path(edge_data_path)
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    tree = ET.parse(str(path))
    root = tree.getroot()
    for interval in root.findall("interval"):
        begin = float(interval.attrib.get("begin", 0))
        end = float(interval.attrib.get("end", 0))
        for edge in interval.findall("edge"):
            attrib = edge.attrib
            rows.append(
                {
                    "sumo_edge_id": attrib.get("id"),
                    "begin_second": int(begin),
                    "end_second": int(end),
                    "mean_speed_mps": _to_float(attrib.get("speed")),
                    "density": _to_float(attrib.get("density")),
                    "occupancy": _to_float(attrib.get("occupancy")),
                    "waiting_time_sec": _to_float(attrib.get("waitingTime")),
                    "time_loss_sec": _to_float(attrib.get("timeLoss")),
                    "departed": _to_int(attrib.get("departed")),
                    "arrived": _to_int(attrib.get("arrived")),
                    "raw": dict(attrib),
                }
            )
    return rows


def build_run_metrics(run_dir: str | Path) -> dict[str, Any]:
    """Combines tripinfo + summary parsing into the full sumo_run_metrics
    payload shape (spec section K)."""
    run_dir = Path(run_dir)
    trip_metrics = parse_tripinfo(run_dir / "tripinfo.xml")
    summary_metrics = parse_summary(run_dir / "summary.xml")

    total_departed = summary_metrics.get("total_departed")
    total_arrived = trip_metrics.get("total_arrived")
    completed_ratio = None
    if total_departed and total_departed > 0 and total_arrived is not None:
        completed_ratio = total_arrived / total_departed

    payload = {
        "total_departed": total_departed,
        "total_arrived": total_arrived,
        "total_loaded": summary_metrics.get("total_loaded"),
        "completed_ratio": completed_ratio,
        "average_travel_time_sec": trip_metrics.get("average_travel_time_sec"),
        "average_waiting_time_sec": trip_metrics.get("average_waiting_time_sec"),
        "average_time_loss_sec": trip_metrics.get("average_time_loss_sec"),
        "total_time_loss_sec": trip_metrics.get("total_time_loss_sec"),
        "average_speed_mps": trip_metrics.get("average_speed_mps"),
        "total_teleports": summary_metrics.get("total_teleports", 0),
    }
    return {**payload, "metrics_payload": payload}


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None
