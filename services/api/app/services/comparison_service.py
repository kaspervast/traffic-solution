"""Baseline vs scenario comparison (spec sections K, L).

Pure, deterministic computation over two sumo_run_metrics rows (+ optional
per-edge metrics) -- no AI involved. Gemini only summarizes the *output* of
this module (see gemini_service.summarize_scenario_result); it never
computes the deltas itself.
"""

from __future__ import annotations

from typing import Any, Literal

Impact = Literal["better", "worse", "unchanged"]


def _pct_change(baseline: float | None, scenario: float | None) -> float | None:
    if baseline is None or scenario is None or baseline == 0:
        return None
    return round((scenario - baseline) / baseline * 100, 2)


def compute_overall_delta(baseline_metrics: dict[str, Any], scenario_metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "average_travel_time_change_percent": _pct_change(
            baseline_metrics.get("average_travel_time_sec"), scenario_metrics.get("average_travel_time_sec")
        ),
        "average_waiting_time_change_percent": _pct_change(
            baseline_metrics.get("average_waiting_time_sec"), scenario_metrics.get("average_waiting_time_sec")
        ),
        "completed_ratio_change_percent": _pct_change(
            baseline_metrics.get("completed_ratio"), scenario_metrics.get("completed_ratio")
        ),
        "teleport_delta": (scenario_metrics.get("total_teleports") or 0) - (baseline_metrics.get("total_teleports") or 0),
    }


def compute_edge_impacts(
    baseline_edges: list[dict[str, Any]], scenario_edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Both lists are rows shaped like metrics_parser.parse_edge_data()
    output (spec section G/K): sumo_edge_id, mean_speed_mps, waiting_time_sec, ..."""
    baseline_by_edge = {row["sumo_edge_id"]: row for row in baseline_edges}
    impacts: list[dict[str, Any]] = []
    for row in scenario_edges:
        edge_id = row["sumo_edge_id"]
        base_row = baseline_by_edge.get(edge_id)
        if base_row is None:
            continue
        speed_change = _pct_change(base_row.get("mean_speed_mps"), row.get("mean_speed_mps"))
        wait_base = base_row.get("waiting_time_sec") or 0
        wait_scenario = row.get("waiting_time_sec") or 0
        waiting_change = round(wait_scenario - wait_base, 2)

        impact: Impact = "unchanged"
        if speed_change is not None and speed_change < -5:
            impact = "worse"
        elif waiting_change > 5:
            impact = "worse"
        elif speed_change is not None and speed_change > 5 and waiting_change <= 0:
            impact = "better"

        impacts.append(
            {
                "sumo_edge_id": edge_id,
                "road_name": row.get("road_name"),
                "speed_change_percent": speed_change,
                "waiting_time_change_sec": waiting_change,
                "impact": impact,
            }
        )
    impacts.sort(key=lambda r: (r["waiting_time_change_sec"] or 0), reverse=True)
    return impacts


def recommend(overall_delta: dict[str, Any], edge_impacts: list[dict[str, Any]]) -> str:
    """Deterministic recommendation, never AI-generated (spec L requires
    an explicit recommendation field; Gemini may only *explain* it)."""
    worse_count = sum(1 for e in edge_impacts if e["impact"] == "worse")
    teleport_delta = overall_delta.get("teleport_delta") or 0
    travel_time_change = overall_delta.get("average_travel_time_change_percent")

    if teleport_delta > 0 or (travel_time_change is not None and travel_time_change > 15):
        return "reject"
    if travel_time_change is None and not edge_impacts:
        return "needs_more_data"
    if worse_count == 0 and (travel_time_change is None or travel_time_change <= 5):
        return "approve_for_field_review"
    return "needs_more_data"


def build_comparison(
    scenario_id: str,
    baseline_run_id: str,
    scenario_run_id: str,
    baseline_metrics: dict[str, Any],
    scenario_metrics: dict[str, Any],
    baseline_edges: list[dict[str, Any]] | None = None,
    scenario_edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    overall_delta = compute_overall_delta(baseline_metrics, scenario_metrics)
    edge_impacts = compute_edge_impacts(baseline_edges or [], scenario_edges or [])
    recommendation = recommend(overall_delta, edge_impacts)
    return {
        "scenario_id": scenario_id,
        "baseline_run_id": baseline_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_delta": overall_delta,
        "edge_impacts": edge_impacts,
        "recommendation": recommendation,
    }
