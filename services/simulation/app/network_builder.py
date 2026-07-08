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

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import ensure_sumo_tools_on_path, get_simulation_settings

# Pilot-scope guardrail (mirrors the "1 km pilot only" framing used
# throughout this MVP): this tool is for small pilot-style bboxes, not
# city-wide extracts. ~0.1 degree is roughly 10km at Rajkot's latitude.
MAX_BBOX_DEGREES = 0.1

# Both the OSM main API and Overpass usage policies expect a descriptive
# User-Agent identifying the application; a generic/default UA can get
# rejected. Sent on every OSM-data request below.
_OSM_USER_AGENT = "Rajkot-AI-Traffic-Platform/0.1 (+SUMO network builder)"

# OSM extract sources, tried in order (spec section E download step). Each
# entry is (label, url_template) where the template takes {bbox} as
# "minLon,minLat,maxLon,maxLat" -- both sources use that exact ordering, so
# no coordinate conversion is needed.
#
# Primary is the OpenStreetMap main API: a completely separate service from
# Overpass, fast, and returns the same OSM XML format netconvert consumes.
# It caps at 0.25 sq degrees / 50000 nodes -- our MAX_BBOX_DEGREES guardrail
# keeps area <= 0.01 sq degrees, and the node cap is only a risk for a very
# large/dense box, which is exactly what the Overpass fallback covers (no
# node limit). Keeping Overpass second also means that if the OSM API is
# ever the one having a bad day, network builds still work.
_OSM_SOURCES = [
    ("OpenStreetMap API", "https://api.openstreetmap.org/api/0.6/map?bbox={bbox}"),
    ("Overpass API", "https://overpass-api.de/api/map?bbox={bbox}"),
]

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


# ---------------------------------------------------------------------------
# Network Builder pipeline: OSM download + demand generation (extends spec
# section E, which previously assumed the .osm.xml already existed on disk
# -- see scenarios/rajkot_pilot/README.md for the manual `curl` command this
# now automates).
# ---------------------------------------------------------------------------


def validate_bbox_size(bbox: str, max_degrees: float = MAX_BBOX_DEGREES) -> tuple[float, float, float, float]:
    """Parses and sanity-checks a "minLon,minLat,maxLon,maxLat" bbox string.
    Raises ValueError (caller maps this to HTTP 400) if the bbox is
    malformed, inverted, or larger than this pilot-scope tool supports.
    Returns (min_lon, min_lat, max_lon, max_lat) on success."""
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError('bbox must be "minLon,minLat,maxLon,maxLat"')
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"bbox values must be numeric: {bbox!r}") from exc

    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError(f"bbox min must be less than max for both lon and lat: {bbox!r}")

    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    if lon_span > max_degrees or lat_span > max_degrees:
        raise ValueError(
            f"bbox too large ({lon_span:.4f} x {lat_span:.4f} degrees); this tool is scoped to "
            f"small pilot-style areas, max {max_degrees} degrees (~10km) per side"
        )
    return min_lon, min_lat, max_lon, max_lat


def slugify(name: str) -> str:
    """Filesystem-safe slug: lowercase alphanumeric + hyphens only. Used to
    derive the scenario directory name from a user-supplied scenario name."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-").lower()
    if not slug:
        raise ValueError("name must contain at least one alphanumeric character")
    return slug


def _fetch_osm_source(label: str, url: str, bbox: str, attempts: int) -> tuple[bytes | None, str]:
    """Tries one OSM source up to `attempts` times with a short backoff for
    transient blips. Returns (content, "") on success, or (None, last_error)
    if this source is exhausted. A definitive 4xx (other than 429 rate
    limit) is treated as non-retryable for this source -- e.g. the OSM API
    returns 400 when a bbox exceeds its node/area limit, in which case
    retrying the same source is pointless and the caller should move on to
    the next source immediately rather than burn the backoff budget."""
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.get(
                url,
                timeout=httpx.Timeout(120.0, connect=15.0),
                headers={"User-Agent": _OSM_USER_AGENT},
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            last_error = f"{label} request failed for bbox={bbox}: {exc}"
        else:
            if response.status_code == 200:
                return response.content, ""
            last_error = (
                f"{label} returned HTTP {response.status_code} for bbox={bbox}: "
                f"{response.text[:300]}"
            )
            # Non-retryable client errors (bad/too-large bbox etc.), except
            # 429 which is a genuine "try again later" -- give up on THIS
            # source right away so we fall through to the next one.
            if 400 <= response.status_code < 500 and response.status_code != 429:
                return None, last_error

        if attempt < attempts:
            time.sleep(3 * attempt)  # 3s, 6s
    return None, last_error


def download_osm_extract(bbox: str, dest_path: str, attempts: int = 2) -> None:
    """Downloads an OSM extract for `bbox` ("minLon,minLat,maxLon,maxLat")
    and writes the raw OSM XML to `dest_path`, trying each source in
    `_OSM_SOURCES` in order until one succeeds. Raises a RuntimeError naming
    every source and its last status only when all sources are exhausted; it
    never silently swallows a failed download.

    Background: the original single-source Overpass fetch broke in
    production when overpass-api.de IP-rate-limited this server (sustained
    HTTP 406 for minutes, reproduced from host and container, curl and
    httpx alike, unaffected by request headers or a full VM reboot). The
    OpenStreetMap main API is a separate service unaffected by that block,
    returns the identical OSM XML format, and uses the same bbox ordering,
    so it is the primary source now with Overpass kept as a fallback for the
    large/dense-bbox case the OSM API rejects (see _OSM_SOURCES)."""
    errors: list[str] = []
    for label, template in _OSM_SOURCES:
        content, err = _fetch_osm_source(label, template.format(bbox=bbox), bbox, attempts)
        if content is not None:
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return
        errors.append(err)

    raise RuntimeError(
        "Could not download an OSM extract from any source for bbox="
        f"{bbox}. Tried: " + " | ".join(errors)
    )


def resolve_random_trips_script() -> tuple[str, str]:
    """Resolves (python_executable, randomTrips.py path), the same careful
    way resolve_netconvert_binary() resolves netconvert: via SUMO_HOME,
    checked for existence rather than assumed. randomTrips.py ships inside
    SUMO_HOME/tools (not a pip package) and is itself a Python script, so it
    must be invoked as `<python> <script path> ...` rather than executed
    directly."""
    settings = get_simulation_settings()
    home = ensure_sumo_tools_on_path(settings.sumo_home)
    script = Path(home) / "tools" / "randomTrips.py"
    if not script.exists():
        raise FileNotFoundError(
            f"randomTrips.py not found at {script} -- check SUMO_HOME ({home}) points at a real SUMO install"
        )
    return sys.executable, str(script)


def generate_demand(
    net_file: str,
    route_file: str,
    begin: int = 0,
    end: int = 3600,
    period: float = 3.0,
    fringe_factor: float = 5.0,
    seed: int = 42,
) -> subprocess.CompletedProcess:
    """Wraps randomTrips.py, mirroring the exact args used for the Rajkot
    baseline demand (scenarios/rajkot_pilot/README.md): --validate,
    --fringe-factor, --seed. Raises CalledProcessError if randomTrips.py
    exits non-zero."""
    python_exe, script = resolve_random_trips_script()
    Path(route_file).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        python_exe,
        script,
        "-n", net_file,
        "-r", route_file,
        "-b", str(begin),
        "-e", str(end),
        "-p", str(period),
        "--validate",
        "--fringe-factor", str(fringe_factor),
        "--seed", str(seed),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
    return result


def count_junctions(net_file: str) -> int:
    """Counts top-level <junction> elements in a .net.xml (excludes the
    internal edges, which are <edge function="internal"> not <junction>)."""
    import xml.etree.ElementTree as ET

    count = 0
    for _, elem in ET.iterparse(net_file, events=("end",)):
        if elem.tag == "junction":
            count += 1
        elem.clear()
    return count


def count_vehicles(route_file: str) -> int:
    """Counts <vehicle>/<trip> elements in a randomTrips.py-generated
    .rou.xml demand file."""
    import xml.etree.ElementTree as ET

    count = 0
    for _, elem in ET.iterparse(route_file, events=("end",)):
        if elem.tag in ("vehicle", "trip"):
            count += 1
        elem.clear()
    return count
