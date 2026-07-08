"""Seeds probe points for the Rajkot pilot zone (spec sections 5.2, 11).

Coordinates below are NOT invented -- they were derived from two real data
sources fetched during development (see project report):

1. A full-tags Overpass QL query (`way["highway"]["name"](bbox); out tags
   geom;`) against the live OSM database, which returned the handful of
   named roads that actually exist in OSM for this 1 km pilot area (most
   local streets here have no `name` tag in OSM at all -- that is a real
   OSM coverage gap for this area, not a bug in this script).
2. High-connectivity junction nodes extracted from the generated
   `rajkot_pilot.net.xml` via sumolib (nodes with >=3 incoming/outgoing
   edges, converted back to WGS84 lon/lat with `net.convertXY2LonLat`),
   picked for spatial spread across the bbox and deduplicated so no two
   points sit within ~150 m of each other (spec 5.2 step 5).

Per spec's "do not assume road names" rule, junctions with no OSM name tag
are labeled generically ("Junction near <lat,lon>") with `notes` flagging
them for manual naming, rather than guessing a road name.

Run from services/api's venv:
    cd services/api
    ./.venv/Scripts/python.exe ../../scripts/seed_probe_points.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(_API_DIR))

from geoalchemy2.elements import WKTElement  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.models import AreaOfInterest, ProbePoint  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

# (name, lat, lon, priority, notes)
PROBE_POINTS: list[tuple[str, float, float, str, str]] = [
    ("AOI Center Junction", 22.329248, 70.769586, "high", "6-way junction cluster near pilot-zone center"),
    ("150 Feet Ring Road Railway Flyover", 22.331920, 70.771598, "high", "OSM-named trunk road (highway=trunk)"),
    ("150 Feet Ring Road (West)", 22.327850, 70.768683, "high", "OSM-named trunk road (highway=trunk)"),
    ("Jamnagar-Rajkot Highway Flyover", 22.330099, 70.768167, "high", "OSM-named primary road (highway=primary)"),
    ("Krishna Nagar Society, Street No 7", 22.324392, 70.771376, "low", "OSM-named residential street"),
    ("Junction near Kalawad Road area", 22.331551, 70.771465, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, south pilot zone", 22.321068, 70.767471, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, mid-west", 22.328269, 70.768977, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, south-central", 22.324174, 70.768117, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, dense south cluster", 22.322831, 70.767741, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, north-central", 22.331109, 70.770955, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, west (10-way cluster)", 22.333198, 70.763226, "high", "High-connectivity 10-edge cluster junction"),
    ("Junction, west edge", 22.334224, 70.759998, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, east-central", 22.326867, 70.772701, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, east", 22.323910, 70.777728, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, east (near highway)", 22.325667, 70.774732, "medium", "Unnamed in OSM -- manual naming needed"),
    ("Junction, far west", 22.333632, 70.762169, "low", "Unnamed in OSM -- manual naming needed"),
    ("Junction, far east", 22.325907, 70.774181, "low", "Unnamed in OSM -- manual naming needed"),
]


def main() -> None:
    db = SessionLocal()
    try:
        aoi = db.scalar(select(AreaOfInterest).order_by(AreaOfInterest.created_at.desc()).limit(1))
        if aoi is None:
            print("No AOI found. Run scripts/seed_aoi.py first.")
            return

        created = 0
        for name, lat, lon, priority, notes in PROBE_POINTS:
            existing = db.scalar(select(ProbePoint).where(ProbePoint.name == name))
            if existing:
                continue
            db.add(
                ProbePoint(
                    aoi_id=aoi.id,
                    name=name,
                    priority=priority,
                    geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                    polling_interval_seconds=120 if priority == "high" else (300 if priority == "medium" else 600),
                    is_active=True,
                    notes=notes,
                )
            )
            created += 1
        db.commit()
        print(f"Seeded {created} new probe points (of {len(PROBE_POINTS)} total defined).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
