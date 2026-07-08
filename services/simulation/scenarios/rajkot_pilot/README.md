# Rajkot Pilot SUMO Scenario

Network + demand assets for the Rajkot 1 km pilot zone (spec section E/F).

- Center: `22.329077,70.769564`, radius 1000 m
- BBox (minLon,minLat,maxLon,maxLat): `70.759854,22.320094,70.779274,22.338060`

## Generation commands (already run once; outputs committed under `network/` and `demand/`)

```bash
# 1. OSM extract (Overpass API "map" export)
curl -o network/rajkot_pilot.osm.xml \
  "https://overpass-api.de/api/map?bbox=70.759854,22.320094,70.779274,22.338060"

# 2. netconvert -> SUMO network (left-hand traffic, India)
netconvert \
  --osm-files network/rajkot_pilot.osm.xml \
  -o network/rajkot_pilot.net.xml \
  --geometry.remove \
  --junctions.join \
  --tls.guess-signals \
  --tls.discard-simple \
  --tls.join \
  --tls.default-type actuated \
  --lefthand true

# 3. Synthetic baseline demand (randomTrips.py, ships in SUMO_HOME/tools)
python "$SUMO_HOME/tools/randomTrips.py" \
  -n network/rajkot_pilot.net.xml \
  -r demand/baseline.rou.xml \
  -b 0 -e 3600 -p 3.0 \
  --validate --fringe-factor 5 --seed 42
```

Result (this build): 7812 `<edge>` elements in the raw net.xml (1667 non-internal
routable edges after filtering junction-internal segments), 1934 junctions.
1200 vehicles in `demand/baseline.rou.xml` (3600s / 3.0s insertion period).

## Known limitations (read before trusting any number from this network)

- **Synthetic demand only.** `baseline.rou.xml` comes from `randomTrips.py`
  with uniform random OD pairs, not real traffic counts. Treat all SUMO
  outputs as planning estimates, not measurements, until calibrated against
  TomTom-observed speeds (spec section F calibration loop) and/or real
  traffic counts.
- **Static route file + rerouting device required for scenarios to have any
  effect.** SUMO vehicles in `baseline.rou.xml` carry a single pre-computed
  route each. A `<rerouter>`/`<closingReroute>` additional file (the
  synchronous `/run-scenario` path in `scenario_runner.py`) only changes
  simulated outcomes if vehicles carry a rerouting device
  (`--device.rerouting.probability 1.0`, enabled by default in
  `scenario_runner.py::_execute_sumo`). Even with that device enabled,
  single-edge closures on this small, densely-connected grid frequently
  produced **no measurable aggregate delta** during development testing --
  the network has short redundant alternate paths for most edges tried.
  A hard closure via TraCI (`traci.edge.setDisallowed`, see
  `app/traci_runner.py`) reliably produces a large, clearly measurable
  effect instead (confirmed: 165 teleport/gridlock events and arrivals
  dropping from 1159/1200 to 721/1195 by the 3600s cutoff, vs. 0 teleports
  in baseline). **For scenario types where a visible impact is important
  (road closures especially), prefer the TraCI runtime path or combine
  multiple contiguous edge changes.**
- **1 km pilot only.** Do not extrapolate results to the wider city.
