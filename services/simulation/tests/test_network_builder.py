"""Unit tests for the Network Builder pipeline's pure-logic pieces (bbox
size validation, slugify, and net.xml/route.xml element counting). These
are exercised with small synthetic XML fixtures -- no Overpass, netconvert,
or randomTrips.py required, matching the style of test_metrics_parser.py.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app import network_builder
from app.network_builder import (
    count_junctions,
    count_vehicles,
    download_osm_extract,
    slugify,
    validate_bbox_size,
)


# ---------------------------------------------------------------------------
# validate_bbox_size
# ---------------------------------------------------------------------------


def test_validate_bbox_size_accepts_pilot_scale_bbox():
    # The real Rajkot pilot bbox (~2km x 2km).
    result = validate_bbox_size("70.759854,22.320094,70.779274,22.338060")
    assert result == (70.759854, 22.320094, 70.779274, 22.338060)


def test_validate_bbox_size_rejects_too_large():
    with pytest.raises(ValueError, match="too large"):
        validate_bbox_size("70.0,22.0,70.5,22.5")  # 0.5 degree ~ 55km


def test_validate_bbox_size_rejects_inverted_bounds():
    with pytest.raises(ValueError, match="min must be less than max"):
        validate_bbox_size("70.5,22.0,70.0,22.5")


def test_validate_bbox_size_rejects_malformed_string():
    with pytest.raises(ValueError):
        validate_bbox_size("70.0,22.0,70.1")  # only 3 parts


def test_validate_bbox_size_rejects_non_numeric():
    with pytest.raises(ValueError, match="numeric"):
        validate_bbox_size("a,b,c,d")


def test_validate_bbox_size_custom_max_degrees():
    # A bbox that fits under the default 0.1 deg cap but not a stricter one.
    validate_bbox_size("70.0,22.0,70.05,22.05")  # 0.05 deg, ok by default
    with pytest.raises(ValueError, match="too large"):
        validate_bbox_size("70.0,22.0,70.05,22.05", max_degrees=0.01)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Evening Peak Closure") == "evening-peak-closure"


def test_slugify_collapses_punctuation():
    assert slugify("  Test_123!!  ") == "test-123"
    assert slugify("a---b") == "a-b"


def test_slugify_rejects_empty_after_stripping():
    with pytest.raises(ValueError):
        slugify("!!!")
    with pytest.raises(ValueError):
        slugify("   ")


# ---------------------------------------------------------------------------
# count_junctions / count_vehicles
# ---------------------------------------------------------------------------

NET_XML = """<?xml version="1.0"?>
<net version="1.16">
  <location netOffset="0,0" convBoundary="0,0,100,100" projParameter="+proj=utm"/>
  <edge id="e1" from="j1" to="j2" function="internal"/>
  <junction id="j1" type="priority" x="0.0" y="0.0"/>
  <junction id="j2" type="priority" x="100.0" y="0.0"/>
  <junction id="j3" type="dead_end" x="50.0" y="50.0"/>
</net>
"""

ROUTE_XML = """<?xml version="1.0"?>
<routes>
  <vehicle id="v0" depart="0.00"><route edges="e1 e2"/></vehicle>
  <vehicle id="v1" depart="1.00"><route edges="e2 e3"/></vehicle>
  <trip id="t0" depart="2.00" from="e1" to="e3"/>
</routes>
"""


def test_count_junctions(tmp_path: Path):
    net_file = tmp_path / "net.xml"
    net_file.write_text(NET_XML, encoding="utf-8")
    assert count_junctions(str(net_file)) == 3


def test_count_vehicles_counts_vehicle_and_trip_elements(tmp_path: Path):
    route_file = tmp_path / "route.rou.xml"
    route_file.write_text(ROUTE_XML, encoding="utf-8")
    assert count_vehicles(str(route_file)) == 3


# ---------------------------------------------------------------------------
# download_osm_extract multi-source fetch
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", text: str = ""):
        self.status_code = status_code
        self.content = content
        self.text = text or content.decode("utf-8", "replace")


def _patch_httpx(monkeypatch, handler):
    """Replace httpx.get with `handler(url) -> _FakeResponse` and neutralize
    the inter-attempt sleep so retry paths don't slow the test down."""
    calls: list[str] = []

    def fake_get(url, *args, **kwargs):
        calls.append(url)
        return handler(url)

    monkeypatch.setattr(network_builder.httpx, "get", fake_get)
    monkeypatch.setattr(network_builder.time, "sleep", lambda *_: None)
    return calls


def test_download_uses_primary_when_it_succeeds(tmp_path: Path, monkeypatch):
    calls = _patch_httpx(monkeypatch, lambda url: _FakeResponse(200, b"<osm/>"))
    dest = tmp_path / "net.osm.xml"

    download_osm_extract("70.0,22.0,70.01,22.01", str(dest))

    assert dest.read_bytes() == b"<osm/>"
    # Only the primary (OSM API) should have been hit; fallback skipped.
    assert len(calls) == 1
    assert "openstreetmap.org" in calls[0]


def test_download_falls_back_to_overpass_on_primary_client_error(tmp_path: Path, monkeypatch):
    # OSM API rejects (e.g. bbox too large / too many nodes -> 400); the
    # Overpass fallback then succeeds. The 400 must be non-retryable so we
    # move to the fallback immediately rather than looping on the primary.
    def handler(url: str) -> _FakeResponse:
        if "openstreetmap.org" in url:
            return _FakeResponse(400, text="You requested too many nodes")
        return _FakeResponse(200, b"<osm-from-overpass/>")

    calls = _patch_httpx(monkeypatch, handler)
    dest = tmp_path / "net.osm.xml"

    download_osm_extract("70.0,22.0,70.09,22.09", str(dest))

    assert dest.read_bytes() == b"<osm-from-overpass/>"
    # Primary hit once (no retry on 400), then the Overpass fallback.
    assert sum("openstreetmap.org" in u for u in calls) == 1
    assert any("overpass-api.de" in u for u in calls)


def test_download_retries_primary_on_transient_then_succeeds(tmp_path: Path, monkeypatch):
    # A transient 429 on the primary should be retried (not treated as a
    # hard client error), and a subsequent 200 should win without ever
    # touching the fallback.
    seq = iter([_FakeResponse(429, text="slow down"), _FakeResponse(200, b"<osm/>")])

    calls = _patch_httpx(monkeypatch, lambda url: next(seq))
    dest = tmp_path / "net.osm.xml"

    download_osm_extract("70.0,22.0,70.01,22.01", str(dest), attempts=2)

    assert dest.read_bytes() == b"<osm/>"
    assert all("openstreetmap.org" in u for u in calls)
    assert len(calls) == 2


def test_download_raises_naming_all_sources_when_all_fail(tmp_path: Path, monkeypatch):
    _patch_httpx(monkeypatch, lambda url: _FakeResponse(406, text="Not Acceptable"))
    dest = tmp_path / "net.osm.xml"

    with pytest.raises(RuntimeError) as exc:
        download_osm_extract("70.0,22.0,70.01,22.01", str(dest), attempts=1)

    msg = str(exc.value)
    assert "OpenStreetMap API" in msg
    assert "Overpass API" in msg
    assert not dest.exists()


def test_download_falls_back_when_primary_connection_errors(tmp_path: Path, monkeypatch):
    # A network-level httpx error on the primary must not abort the whole
    # download -- it should still try the fallback.
    def handler(url: str) -> _FakeResponse:
        if "openstreetmap.org" in url:
            raise httpx.ConnectError("boom")
        return _FakeResponse(200, b"<osm/>")

    _patch_httpx(monkeypatch, handler)
    dest = tmp_path / "net.osm.xml"

    download_osm_extract("70.0,22.0,70.01,22.01", str(dest), attempts=1)

    assert dest.read_bytes() == b"<osm/>"
