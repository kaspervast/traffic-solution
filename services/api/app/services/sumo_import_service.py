"""Reusable SUMO network -> PostGIS import logic (spec section G).

This is the core loop originally written as a one-off in
scripts/import_sumo_edges.py (for the seeded rajkot_pilot network),
refactored out so it can also be called from
POST /api/sumo/networks/import-osm (networks built on demand via the
Network Builder tab) without duplicating the sumolib-shape-to-WKT
conversion logic in two places.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SumoEdge, SumoNetwork


def load_sumolib():
    """Appends SUMO_HOME/tools to sys.path (if not already present) and
    imports sumolib. Separate from app.core.config since this module is
    also imported by the standalone scripts/import_sumo_edges.py CLI."""
    settings = get_settings()
    sumo_home = settings.sumo_home or os.environ.get("SUMO_HOME", "")
    tools_dir = str(Path(sumo_home) / "tools")
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    import sumolib  # type: ignore

    return sumolib


def import_network_to_postgis(
    db: Session,
    net_file: str,
    network_name: str,
    aoi_id: uuid.UUID | None,
    bbox: tuple[float, float, float, float],
    source: str = "osm",
    osm_file: str | None = None,
    sumo_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Creates (or reuses, matched by name) a `sumo_networks` row and
    imports every non-internal edge in `net_file` as a `sumo_edges` row,
    with shapes converted to WGS84 via the network's own projection
    metadata (net.convertXY2LonLat) -- never a guessed projection, per spec
    section G.

    `bbox` is (min_lon, min_lat, max_lon, max_lat).

    Returns {"network_id": str, "created": bool, "edges_created": int,
    "edges_skipped_no_shape": int}.
    """
    sumolib = load_sumolib()
    net = sumolib.net.readNet(net_file, withInternal=False)

    min_lon, min_lat, max_lon, max_lat = bbox

    network = db.scalar(select(SumoNetwork).where(SumoNetwork.name == network_name))
    created = False
    if network is None:
        network = SumoNetwork(
            aoi_id=aoi_id,
            name=network_name,
            sumo_version=sumo_version,
            source=source,
            bbox_min_lat=min_lat,
            bbox_min_lon=min_lon,
            bbox_max_lat=max_lat,
            bbox_max_lon=max_lon,
            net_file_path=net_file,
            osm_file_path=osm_file,
            is_active=True,
            metadata_json=metadata or {},
        )
        db.add(network)
        db.commit()
        db.refresh(network)
        created = True

    existing_edge_ids = set(
        db.scalars(select(SumoEdge.sumo_edge_id).where(SumoEdge.network_id == network.id))
    )

    edges_created = 0
    edges_skipped_no_shape = 0
    for edge in net.getEdges():
        if edge.isSpecial():
            continue
        if edge.getID() in existing_edge_ids:
            continue

        shape_xy = edge.getShape()
        if len(shape_xy) < 2:
            edges_skipped_no_shape += 1
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
        edges_created += 1
        if edges_created % 200 == 0:
            db.commit()

    db.commit()

    return {
        "network_id": str(network.id),
        "created": created,
        "edges_created": edges_created,
        "edges_skipped_no_shape": edges_skipped_no_shape,
    }
