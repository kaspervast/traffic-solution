"""SUMO network build/import helpers (spec section E, G).

Wraps the netconvert workflow used to build services/simulation/scenarios/
rajkot_pilot/network/rajkot_pilot.net.xml from an OSM extract, and exposes
`extract_edges()` which uses sumolib to read the generated .net.xml and
convert edge shapes from SUMO's internal projected coordinates back to
WGS84 lon/lat using the network's own <location netOffset=... proj.../>
metadata (net.convertXY2LonLat). This is the piece the import-into-PostGIS
step (import_edges.py) depends on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import ensure_sumo_tools_on_path, get_simulation_settings

# Recommended netconvert flags for the Rajkot pilot area (spec section E):
# left-hand traffic (India), guess/join traffic signals from OSM data.
NETCONVERT_ARGS = [
    "--geometry.remove",
    "--junctions.join",
    "--tls.guess-signals",
    "--tls.discard-simple",
    "--tls.join",
    "--tls.default-type", "actuated",
    "--lefthand", "true",
]


def resolve_netconvert_binary() -> str:
    settings = get_simulation_settings()
    home = ensure_sumo_tools_on_path(settings.sumo_home)
    import platform

    exe_name = "netconvert.exe" if platform.system() == "Windows" else "netconvert"
    candidate = Path(home) / "bin" / exe_name
    return str(candidate) if candidate.exists() else "netconvert"


def build_network_from_osm(osm_file: str, net_file: str) -> subprocess.CompletedProcess:
    """Runs netconvert to produce net_file from osm_file. Raises
    CalledProcessError if netconvert exits non-zero."""
    binary = resolve_netconvert_binary()
    cmd = [binary, "--osm-files", osm_file, "-o", net_file, *NETCONVERT_ARGS]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
    return result


def validate_network(net_file: str) -> bool:
    """Dry-loads the network with `sumo -n` (no route/demand) to confirm it
    parses without error. Returns True on exit code 0."""
    import platform

    settings = get_simulation_settings()
    home = ensure_sumo_tools_on_path(settings.sumo_home)
    exe_name = "sumo.exe" if platform.system() == "Windows" else "sumo"
    candidate = Path(home) / "bin" / exe_name
    binary = str(candidate) if candidate.exists() else "sumo"
    proc = subprocess.run(
        [binary, "-n", net_file, "--no-step-log", "true", "--begin", "0", "--end", "1"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode == 0


@dataclass
class SumoEdgeRecord:
    sumo_edge_id: str
    from_node: str | None
    to_node: str | None
    road_name: str | None
    priority: int | None
    num_lanes: int
    speed_mps: float
    length_m: float
    lonlat_shape: list[tuple[float, float]]  # [(lon, lat), ...]
    raw: dict[str, Any]


def extract_edges(net_file: str) -> list[SumoEdgeRecord]:
    """Parses a SUMO .net.xml with sumolib and returns edges with WGS84
    (lon, lat) shapes, converted via the network's own projection metadata
    (net.convertXY2LonLat) -- this is the officially recommended way to
    recover real-world coordinates from a SUMO network per spec section G.
    """
    settings = get_simulation_settings()
    ensure_sumo_tools_on_path(settings.sumo_home)
    import sumolib  # type: ignore

    net = sumolib.net.readNet(net_file, withInternal=False)
    records: list[SumoEdgeRecord] = []
    for edge in net.getEdges():
        if edge.isSpecial():
            continue
        shape_xy = edge.getShape()
        shape_lonlat = [net.convertXY2LonLat(x, y) for x, y in shape_xy]
        lanes = edge.getLanes()
        speed_mps = edge.getSpeed()
        length_m = edge.getLength()
        from_node = edge.getFromNode().getID() if edge.getFromNode() else None
        to_node = edge.getToNode().getID() if edge.getToNode() else None
        road_name = edge.getName() or None
        records.append(
            SumoEdgeRecord(
                sumo_edge_id=edge.getID(),
                from_node=from_node,
                to_node=to_node,
                road_name=road_name,
                priority=edge.getPriority(),
                num_lanes=len(lanes),
                speed_mps=speed_mps,
                length_m=length_m,
                lonlat_shape=shape_lonlat,
                raw={
                    "function": edge.getFunction(),
                    "type": edge.getType(),
                },
            )
        )
    return records


def get_network_offset_and_proj(net_file: str) -> dict[str, str]:
    """Reads the <location netOffset=... projParameter=.../> element that
    SUMO writes into every generated network, needed to justify/document how
    coordinates are recovered (spec section G explicitly calls this out)."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(net_file)
    loc = tree.getroot().find("location")
    if loc is None:
        return {}
    return dict(loc.attrib)
