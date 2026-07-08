"""Seeds the Rajkot 1 km pilot AOI (spec section 6 / target area).

Run from services/api's venv (needs app.db.* + DATABASE_URL):
    cd services/api
    ./.venv/Scripts/python.exe ../../scripts/seed_aoi.py

Idempotent: does nothing if an AOI with the configured name already exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a standalone script: add services/api to sys.path so
# `import app.*` resolves regardless of CWD.
_API_DIR = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(_API_DIR))

from geoalchemy2.elements import WKTElement  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import AreaOfInterest  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def build_pilot_polygon_wkt(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    """Simple rectangular bbox polygon (close enough for the MVP AOI
    footprint; the circular 1 km radius is stored separately via radius_m +
    center for any circle-based queries)."""
    return (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def main() -> None:
    settings = get_settings()
    min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox_tuple

    db = SessionLocal()
    try:
        existing = db.scalar(select(AreaOfInterest).where(AreaOfInterest.name == settings.aoi_name))
        if existing:
            print(f"AOI '{settings.aoi_name}' already exists (id={existing.id}); nothing to do.")
            return

        aoi = AreaOfInterest(
            name=settings.aoi_name,
            center=WKTElement(f"POINT({settings.aoi_center_lon} {settings.aoi_center_lat})", srid=4326),
            radius_m=settings.aoi_radius_m,
            bbox_min_lat=min_lat,
            bbox_min_lon=min_lon,
            bbox_max_lat=max_lat,
            bbox_max_lon=max_lon,
            polygon=WKTElement(build_pilot_polygon_wkt(min_lon, min_lat, max_lon, max_lat), srid=4326),
        )
        db.add(aoi)
        db.commit()
        db.refresh(aoi)
        print(f"Seeded AOI '{aoi.name}' (id={aoi.id}) center=({settings.aoi_center_lat},{settings.aoi_center_lon}) radius_m={aoi.radius_m}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
