"""Imports the generated Rajkot SUMO network into PostGIS (spec section G):
creates a `sumo_networks` row and one `sumo_edges` row per non-internal
edge, with shapes converted to WGS84 via sumolib (spec section G explicit
requirement: use the network's own netOffset/projParameter, not a guess).

Run from services/api's venv:
    cd services/api
    ./.venv/Scripts/python.exe ../../scripts/import_sumo_edges.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _REPO_ROOT / "services" / "api"
sys.path.insert(0, str(_API_DIR))

from geoalchemy2.elements import WKTElement  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import AreaOfInterest, SumoEdge, SumoNetwork  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

NET_FILE = _REPO_ROOT / "services/simulation/scenarios/rajkot_pilot/network/rajkot_pilot.net.xml"
OSM_FILE = _REPO_ROOT / "services/simulation/scenarios/rajkot_pilot/network/rajkot_pilot.osm.xml"


def _load_sumolib():
    settings = get_settings()
    sumo_home = settings.sumo_home or os.environ.get("SUMO_HOME", "")
    tools_dir = str(Path(sumo_home) / "tools")
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    import sumolib  # type: ignore

    return sumolib


def main() -> None:
    settings = get_settings()
    sumolib = _load_sumolib()

    net = sumolib.net.readNet(str(NET_FILE), withInternal=False)

    db = SessionLocal()
    try:
        aoi = db.scalar(select(AreaOfInterest).order_by(AreaOfInterest.created_at.desc()).limit(1))

        network = db.scalar(select(SumoNetwork).where(SumoNetwork.name == "rajkot_pilot"))
        if network is None:
            min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox_tuple
            network = SumoNetwork(
                aoi_id=aoi.id if aoi else None,
                name="rajkot_pilot",
                sumo_version="1.27.1",
                source="osm",
                bbox_min_lat=min_lat,
                bbox_min_lon=min_lon,
                bbox_max_lat=max_lat,
                bbox_max_lon=max_lon,
                net_file_path=str(NET_FILE),
                osm_file_path=str(OSM_FILE) if OSM_FILE.exists() else None,
                is_active=True,
                metadata_json={"generated_via": "netconvert --osm-files ... --lefthand true"},
            )
            db.add(network)
            db.commit()
            db.refresh(network)
            print(f"Created sumo_networks row id={network.id}")
        else:
            print(f"Using existing sumo_networks row id={network.id}")

        existing_edge_ids = set(
            db.scalars(
                select(SumoEdge.sumo_edge_id).where(SumoEdge.network_id == network.id)
            )
        )

        created = 0
        skipped_no_shape = 0
        for edge in net.getEdges():
            if edge.isSpecial():
                continue
            if edge.getID() in existing_edge_ids:
                continue

            shape_xy = edge.getShape()
            if len(shape_xy) < 2:
                skipped_no_shape += 1
                continue
            shape_lonlat = [net.convertXY2LonLat(x, y) for x, y in shape_xy]
            wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in shape_lonlat) + ")"

            db.add(
                SumoEdge(
                    network_id=network.id,
                    sumo_edge_id=edge.getID(),
                    from_node=edge.getFromNode().getID() if edge.getFromNode() else None,
                    to_node=edge.getToNode().getID() if edge.getToNode() else None,
                    road_name=edge.getName() or None,
                    priority=edge.getPriority(),
                    num_lanes=len(edge.getLanes()),
                    speed_mps=edge.getSpeed(),
                    length_m=edge.getLength(),
                    geom=WKTElement(wkt, srid=4326),
                    raw={"function": edge.getFunction(), "type": edge.getType()},
                )
            )
            created += 1
            if created % 200 == 0:
                db.commit()

        db.commit()
        print(f"Imported {created} new sumo_edges (skipped {skipped_no_shape} with no shape).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
