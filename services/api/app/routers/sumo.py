"""SUMO endpoints (spec section J)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import require_role
from app.db.models import (
    AIInsight,
    SumoEdge,
    SumoNetwork,
    SumoRunMetrics,
    SumoScenario,
    SumoScenarioComparison,
    SumoSimulationRun,
    TomTomSumoEdgeMapping,
)
from app.db.session import get_db
from app.schemas.sumo import SumoScenarioRequest
from app.services.comparison_service import build_comparison
from app.services.gemini_service import GeminiUnavailableError, summarize_scenario_result
from app.services.sumo_client import SumoServiceClient

router = APIRouter(prefix="/api/sumo", tags=["sumo"])


@router.get("/networks")
def list_networks(db: Session = Depends(get_db)):
    networks = db.scalars(select(SumoNetwork).order_by(SumoNetwork.created_at.desc()))
    return [
        {
            "id": str(n.id),
            "name": n.name,
            "source": n.source,
            "net_file_path": n.net_file_path,
            "is_active": n.is_active,
        }
        for n in networks
    ]


@router.get("/networks/{network_id}")
def get_network(network_id: uuid.UUID, db: Session = Depends(get_db)):
    network = db.get(SumoNetwork, network_id)
    if network is None:
        raise HTTPException(status_code=404, detail="Network not found")
    return {
        "id": str(network.id),
        "name": network.name,
        "net_file_path": network.net_file_path,
        "bbox": [network.bbox_min_lon, network.bbox_min_lat, network.bbox_max_lon, network.bbox_max_lat],
        "metadata": network.metadata_json,
    }


@router.get("/networks/{network_id}/edges")
def get_network_edges(network_id: uuid.UUID, db: Session = Depends(get_db)):
    from geoalchemy2.shape import to_shape

    edges = db.scalars(select(SumoEdge).where(SumoEdge.network_id == network_id))
    out = []
    for e in edges:
        shape = to_shape(e.geom) if e.geom is not None else None
        out.append(
            {
                "id": str(e.id),
                "sumo_edge_id": e.sumo_edge_id,
                "road_name": e.road_name,
                "num_lanes": e.num_lanes,
                "speed_mps": e.speed_mps,
                "length_m": e.length_m,
                "coordinates": list(shape.coords) if shape else [],
            }
        )
    return out


@router.post("/networks/{network_id}/match-tomtom-segments")
def match_tomtom_segments(
    network_id: uuid.UUID,
    max_distance_m: float = 30.0,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
):
    """PostGIS nearest-neighbor matching (spec section G). Requires PostGIS
    (blocked in this environment until the extension is installed -- see
    README known blockers)."""
    sql = text(
        """
        SELECT
          rs.id AS tomtom_road_segment_id,
          se.id AS sumo_edge_db_id,
          ST_Distance(rs.geom::geography, se.geom::geography) AS distance_m
        FROM road_segments rs
        JOIN LATERAL (
          SELECT *
          FROM sumo_edges se
          WHERE se.network_id = :network_id
          ORDER BY se.geom <-> rs.geom
          LIMIT 1
        ) se ON true
        WHERE ST_Distance(rs.geom::geography, se.geom::geography) <= :max_distance
        """
    )
    rows = db.execute(sql, {"network_id": str(network_id), "max_distance": max_distance_m}).mappings().all()

    created = 0
    for row in rows:
        existing = db.scalar(
            select(TomTomSumoEdgeMapping).where(
                TomTomSumoEdgeMapping.road_segment_id == row["tomtom_road_segment_id"],
                TomTomSumoEdgeMapping.sumo_edge_db_id == row["sumo_edge_db_id"],
            )
        )
        if existing:
            continue
        db.add(
            TomTomSumoEdgeMapping(
                road_segment_id=row["tomtom_road_segment_id"],
                sumo_edge_db_id=row["sumo_edge_db_id"],
                match_method="spatial_nearest",
                distance_m=row["distance_m"],
                confidence=max(0.0, 1 - (row["distance_m"] / max_distance_m)),
                review_status="pending",
            )
        )
        created += 1
    db.commit()
    return {"matches_found": len(rows), "new_mappings_created": created}


@router.patch("/edge-mappings/{mapping_id}")
def review_edge_mapping(
    mapping_id: uuid.UUID,
    review_status: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
):
    mapping = db.get(TomTomSumoEdgeMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    if review_status not in ("pending", "approved", "rejected", "manual_override"):
        raise HTTPException(status_code=400, detail="Invalid review_status")
    mapping.review_status = review_status
    db.commit()
    return {"id": str(mapping.id), "review_status": mapping.review_status}


@router.post("/scenarios")
def create_scenario(
    payload: SumoScenarioRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
):
    scenario = SumoScenario(
        aoi_id=payload.aoi_id,
        network_id=payload.network_id,
        name=payload.name,
        scenario_type=payload.scenario_type,
        description=payload.description,
        scenario_payload=payload.model_dump(mode="json"),
        created_by=payload.created_by,
        human_review_status="draft",
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return {"id": str(scenario.id), "human_review_status": scenario.human_review_status}


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.scalars(select(SumoScenario).order_by(SumoScenario.created_at.desc()))
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "scenario_type": s.scenario_type,
            "human_review_status": s.human_review_status,
            "created_at": s.created_at.isoformat(),
        }
        for s in scenarios
    ]


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: uuid.UUID, db: Session = Depends(get_db)):
    scenario = db.get(SumoScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "id": str(scenario.id),
        "name": scenario.name,
        "scenario_type": scenario.scenario_type,
        "scenario_payload": scenario.scenario_payload,
        "human_review_status": scenario.human_review_status,
    }


@router.post("/scenarios/{scenario_id}/run")
async def run_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_role("operator")),
):
    scenario = db.get(SumoScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.human_review_status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Scenario must be approved by a human before it can be run (spec section B rule 10).",
        )

    run = SumoSimulationRun(scenario_id=scenario.id, run_type="scenario", status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    client = SumoServiceClient()
    try:
        result = await client.run_scenario(scenario.scenario_payload)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Simulation service call failed: {exc}")

    run.status = result.get("status", "failed")
    run.run_dir = result.get("run_dir")
    db.commit()

    metrics_payload = result.get("metrics", {})
    db.add(
        SumoRunMetrics(
            run_id=run.id,
            total_arrived=metrics_payload.get("total_arrived"),
            average_travel_time_sec=metrics_payload.get("average_duration_sec")
            or metrics_payload.get("average_travel_time_sec"),
            average_waiting_time_sec=metrics_payload.get("average_waiting_time_sec"),
            average_time_loss_sec=metrics_payload.get("average_time_loss_sec"),
            total_time_loss_sec=metrics_payload.get("total_time_loss_sec"),
            metrics_payload=metrics_payload,
        )
    )
    db.commit()
    return {"run_id": str(run.id), "status": run.status, "metrics": metrics_payload}


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(SumoSimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": str(run.id),
        "run_type": run.run_type,
        "status": run.status,
        "run_dir": run.run_dir,
        "error_message": run.error_message,
    }


@router.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: uuid.UUID, db: Session = Depends(get_db)):
    metrics = db.scalar(
        select(SumoRunMetrics).where(SumoRunMetrics.run_id == run_id).order_by(SumoRunMetrics.created_at.desc())
    )
    if metrics is None:
        raise HTTPException(status_code=404, detail="No metrics stored for this run yet")
    return metrics.metrics_payload


@router.get("/runs/{run_id}/files")
def get_run_files(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(SumoSimulationRun, run_id)
    if run is None or not run.run_dir:
        raise HTTPException(status_code=404, detail="Run or run directory not found")
    return {
        "run_dir": run.run_dir,
        "files": ["scenario.sumocfg", "tripinfo.xml", "summary.xml", "edgeData.xml", "run.log"],
    }


@router.post("/runs/{run_id}/summarize-with-gemini")
def summarize_run_with_gemini(run_id: uuid.UUID, baseline_run_id: uuid.UUID, db: Session = Depends(get_db)):
    scenario_metrics = db.scalar(
        select(SumoRunMetrics).where(SumoRunMetrics.run_id == run_id).order_by(SumoRunMetrics.created_at.desc())
    )
    baseline_metrics = db.scalar(
        select(SumoRunMetrics)
        .where(SumoRunMetrics.run_id == baseline_run_id)
        .order_by(SumoRunMetrics.created_at.desc())
    )
    if scenario_metrics is None or baseline_metrics is None:
        raise HTTPException(status_code=409, detail="Both baseline and scenario metrics must exist first")

    scenario_run = db.get(SumoSimulationRun, run_id)
    comparison = build_comparison(
        scenario_id=str(scenario_run.scenario_id) if scenario_run else "",
        baseline_run_id=str(baseline_run_id),
        scenario_run_id=str(run_id),
        baseline_metrics=baseline_metrics.metrics_payload,
        scenario_metrics=scenario_metrics.metrics_payload,
    )

    try:
        summary = summarize_scenario_result(comparison)
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    insight = AIInsight(
        insight_type="sumo_scenario_summary",
        model_name="gemini",
        prompt_version="v1",
        input_payload=comparison,
        output_payload=summary.model_dump(),
        confidence=summary.confidence,
        human_review_status="pending",
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    db.add(
        SumoScenarioComparison(
            baseline_run_id=baseline_run_id,
            scenario_run_id=run_id,
            comparison_payload=comparison,
            gemini_summary_insight_id=insight.id,
        )
    )
    db.commit()

    return {"comparison": comparison, "gemini_summary": summary.model_dump(), "ai_insight_id": str(insight.id)}
