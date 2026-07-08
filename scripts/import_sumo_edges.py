"""Imports the generated Rajkot SUMO network into PostGIS (spec section G):
creates a `sumo_networks` row and one `sumo_edges` row per non-internal
edge, with shapes converted to WGS84 via sumolib (spec section G explicit
requirement: use the network's own netOffset/projParameter, not a guess).

Thin CLI wrapper around app.services.sumo_import_service.import_network_to_postgis
-- the actual sumolib-shape-to-WKT / DB-writing loop lives there so both
this script and POST /api/sumo/networks/import-osm share one implementation.

Run from services/api's venv:
    cd services/api
    ./.venv/Scripts/python.exe ../../scripts/import_sumo_edges.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _REPO_ROOT / "services" / "api"
sys.path.insert(0, str(_API_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import AreaOfInterest  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.sumo_import_service import import_network_to_postgis  # noqa: E402

NET_FILE = _REPO_ROOT / "services/simulation/scenarios/rajkot_pilot/network/rajkot_pilot.net.xml"
OSM_FILE = _REPO_ROOT / "services/simulation/scenarios/rajkot_pilot/network/rajkot_pilot.osm.xml"


def main() -> None:
    settings = get_settings()

    db = SessionLocal()
    try:
        aoi = db.scalar(select(AreaOfInterest).order_by(AreaOfInterest.created_at.desc()).limit(1))

        result = import_network_to_postgis(
            db=db,
            net_file=str(NET_FILE),
            network_name="rajkot_pilot",
            aoi_id=aoi.id if aoi else None,
            bbox=settings.aoi_bbox_tuple,
            source="osm",
            osm_file=str(OSM_FILE) if OSM_FILE.exists() else None,
            sumo_version="1.27.1",
            metadata={"generated_via": "netconvert --osm-files ... --lefthand true"},
        )
        if result["created"]:
            print(f"Created sumo_networks row id={result['network_id']}")
        else:
            print(f"Using existing sumo_networks row id={result['network_id']}")
        print(
            f"Imported {result['edges_created']} new sumo_edges "
            f"(skipped {result['edges_skipped_no_shape']} with no shape)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
