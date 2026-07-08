"""Unit tests for app.services.sumo_import_service.import_edges_to_postgis
(the SUMO-less import path used by POST /api/sumo/networks/import-osm, which
takes edges the simulation service already extracted).

Uses a mocked SQLAlchemy Session (no live Postgres/PostGIS), matching the
style of test_scenario_context_service.py -- the function only calls
db.scalar/db.scalars/db.add/db.commit/db.refresh, so those are stubbed and
the added SumoEdge objects are inspected directly.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.db.models import SumoEdge, SumoNetwork
from app.services.sumo_import_service import import_edges_to_postgis

AOI_ID = uuid.uuid4()
BBOX = (70.76, 22.32, 70.78, 22.34)


def _edge(edge_id: str, shape):
    return {
        "sumo_edge_id": edge_id,
        "from_node": "n1",
        "to_node": "n2",
        "road_name": None,
        "priority": 3,
        "num_lanes": 2,
        "speed_mps": 13.9,
        "length_m": 42.0,
        "lonlat_shape": shape,
        "raw": {"function": "normal", "type": "highway.residential"},
    }


def _new_network_session():
    """A Session mock where no network exists yet (so one is created) and no
    edges exist yet."""
    db = MagicMock()
    db.scalar.return_value = None  # SumoNetwork lookup -> not found -> create
    db.scalars.return_value = []  # existing edge ids -> none
    return db


def test_imports_valid_edges_and_skips_short_shapes():
    db = _new_network_session()
    edges = [
        _edge("e1", [[70.77, 22.33], [70.771, 22.331]]),
        _edge("e2", [[70.772, 22.332], [70.773, 22.333], [70.774, 22.334]]),
        _edge("e3", [[70.775, 22.335]]),  # single point -> skipped
        _edge("e4", []),  # no shape -> skipped
    ]

    result = import_edges_to_postgis(
        db=db, edges=edges, network_name="area-x", aoi_id=AOI_ID, bbox=BBOX
    )

    assert result["created"] is True
    assert result["edges_created"] == 2
    assert result["edges_skipped_no_shape"] == 2

    added = [c.args[0] for c in db.add.call_args_list]
    networks = [a for a in added if isinstance(a, SumoNetwork)]
    sumo_edges = [a for a in added if isinstance(a, SumoEdge)]
    assert len(networks) == 1
    assert {e.sumo_edge_id for e in sumo_edges} == {"e1", "e2"}
    # WKT is built from the lon/lat pairs in order.
    e1 = next(e for e in sumo_edges if e.sumo_edge_id == "e1")
    assert str(e1.geom.data) == "LINESTRING(70.77 22.33, 70.771 22.331)"


def test_skips_edges_already_present_for_this_network():
    db = _new_network_session()
    db.scalars.return_value = ["e1"]  # e1 already imported for this network

    result = import_edges_to_postgis(
        db=db,
        edges=[
            _edge("e1", [[70.77, 22.33], [70.771, 22.331]]),
            _edge("e2", [[70.772, 22.332], [70.773, 22.333]]),
        ],
        network_name="area-x",
        aoi_id=AOI_ID,
        bbox=BBOX,
    )

    assert result["edges_created"] == 1
    sumo_edges = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], SumoEdge)]
    assert {e.sumo_edge_id for e in sumo_edges} == {"e2"}


def test_reuses_existing_network_matched_by_name():
    db = MagicMock()
    existing = SumoNetwork(name="area-x")
    db.scalar.return_value = existing  # network already exists
    db.scalars.return_value = []

    result = import_edges_to_postgis(
        db=db,
        edges=[_edge("e1", [[70.77, 22.33], [70.771, 22.331]])],
        network_name="area-x",
        aoi_id=AOI_ID,
        bbox=BBOX,
    )

    assert result["created"] is False
    assert result["edges_created"] == 1
    # No new SumoNetwork should have been added, only the edge.
    added = [c.args[0] for c in db.add.call_args_list]
    assert not any(isinstance(a, SumoNetwork) for a in added)
