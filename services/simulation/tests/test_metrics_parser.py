"""Unit tests for SUMO output parsing (spec section K).

Uses small synthetic tripinfo/summary/edgeData XML fixtures written to a
temp dir -- these exercise the same parsing code that was also verified
against a real SUMO run's outputs (see services/simulation/runs and the
project report), but keep the automated test suite fast and independent of
having SUMO installed.
"""

from __future__ import annotations

from pathlib import Path

from app.metrics_parser import build_run_metrics, parse_edge_data, parse_summary, parse_tripinfo

TRIPINFO_XML = """<?xml version="1.0"?>
<tripinfos>
  <tripinfo id="0" duration="120.0" waitingTime="5.0" timeLoss="20.0" routeLength="1000.0"/>
  <tripinfo id="1" duration="80.0" waitingTime="0.0" timeLoss="10.0" routeLength="600.0"/>
  <tripinfo id="2" duration="200.0" waitingTime="15.0" timeLoss="60.0" routeLength="1800.0"/>
</tripinfos>
"""

SUMMARY_XML = """<?xml version="1.0"?>
<summary>
  <step time="0.00" loaded="10" inserted="0" running="0" waiting="0" ended="0" arrived="0" collisions="0" teleports="0"/>
  <step time="1.00" loaded="10" inserted="5" running="5" waiting="0" ended="0" arrived="0" collisions="0" teleports="1"/>
  <step time="2.00" loaded="10" inserted="10" running="7" waiting="0" ended="3" arrived="3" collisions="0" teleports="0"/>
</summary>
"""

EDGE_DATA_XML = """<?xml version="1.0"?>
<meandata>
  <interval begin="0.00" end="3600.00" id="dump">
    <edge id="edgeA" sampledSeconds="120.5" speed="10.5" density="0.05" occupancy="0.02" waitingTime="3.0" timeLoss="4.5" departed="1" arrived="2"/>
    <edge id="edgeB" sampledSeconds="60.0" speed="8.2" density="0.03" occupancy="0.01" waitingTime="0.0" timeLoss="1.0" departed="0" arrived="0"/>
  </interval>
</meandata>
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_tripinfo_averages(tmp_path: Path):
    path = _write(tmp_path, "tripinfo.xml", TRIPINFO_XML)
    metrics = parse_tripinfo(path)
    assert metrics["total_arrived"] == 3
    assert metrics["average_travel_time_sec"] == (120.0 + 80.0 + 200.0) / 3
    assert metrics["average_waiting_time_sec"] == (5.0 + 0.0 + 15.0) / 3
    assert metrics["average_time_loss_sec"] == (20.0 + 10.0 + 60.0) / 3
    assert metrics["total_time_loss_sec"] == 90.0


def test_parse_tripinfo_missing_file_returns_zeroed_defaults(tmp_path: Path):
    metrics = parse_tripinfo(tmp_path / "does_not_exist.xml")
    assert metrics["total_arrived"] == 0
    assert metrics["average_travel_time_sec"] is None


def test_parse_summary_reads_final_step_and_max_teleports(tmp_path: Path):
    path = _write(tmp_path, "summary.xml", SUMMARY_XML)
    metrics = parse_summary(path)
    assert metrics["total_departed"] == 10  # "inserted" at final step
    assert metrics["total_loaded"] == 10
    assert metrics["total_teleports"] == 1  # max seen across steps


def test_parse_edge_data_rows(tmp_path: Path):
    path = _write(tmp_path, "edgeData.xml", EDGE_DATA_XML)
    rows = parse_edge_data(path)
    assert len(rows) == 2
    edge_a = next(r for r in rows if r["sumo_edge_id"] == "edgeA")
    assert edge_a["mean_speed_mps"] == 10.5
    assert edge_a["waiting_time_sec"] == 3.0
    assert edge_a["departed"] == 1
    assert edge_a["arrived"] == 2
    assert edge_a["begin_second"] == 0
    assert edge_a["end_second"] == 3600


def test_build_run_metrics_combines_tripinfo_and_summary(tmp_path: Path):
    _write(tmp_path, "tripinfo.xml", TRIPINFO_XML)
    _write(tmp_path, "summary.xml", SUMMARY_XML)
    metrics = build_run_metrics(tmp_path)
    assert metrics["total_departed"] == 10
    assert metrics["total_arrived"] == 3
    assert metrics["completed_ratio"] == 3 / 10
    assert metrics["total_teleports"] == 1
    assert "metrics_payload" in metrics
    assert metrics["metrics_payload"]["total_arrived"] == 3


def test_build_run_metrics_handles_missing_files_gracefully(tmp_path: Path):
    metrics = build_run_metrics(tmp_path)
    assert metrics["total_arrived"] == 0
    assert metrics["completed_ratio"] is None
