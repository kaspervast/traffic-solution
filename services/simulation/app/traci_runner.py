"""Optional TraCI runtime runner (spec section Q).

Used for scenario types that need mid-simulation changes (e.g. reduce_speed
edge changes, signal timing changes) that the static scenario_runner.py
additional-file approach cannot express well. Kept close to the spec's base
code; only the sys.path bootstrap is delegated to app.config so both this
module and network_builder.py resolve SUMO_HOME consistently on Windows.
"""

from __future__ import annotations

from typing import Any

from app.config import ensure_sumo_tools_on_path, get_simulation_settings

ensure_sumo_tools_on_path(get_simulation_settings().sumo_home)

import traci  # type: ignore  # noqa: E402


class TraciScenarioRunner:
    def __init__(self, sumo_binary: str = "sumo") -> None:
        self.sumo_binary = sumo_binary

    def run_with_runtime_changes(self, sumocfg_path: str, scenario_config: dict[str, Any]) -> dict[str, Any]:
        traci.start([self.sumo_binary, "-c", sumocfg_path, "--no-step-log", "true"])
        try:
            begin = int(scenario_config.get("simulation_start_second", 0))
            end = int(scenario_config.get("simulation_end_second", 3600))
            for t in range(begin, end):
                for change in scenario_config.get("edge_changes", []):
                    if int(change.get("start_second", 0)) <= t <= int(change.get("end_second", 3600)):
                        if change["action"] == "reduce_speed":
                            traci.edge.setMaxSpeed(change["sumo_edge_id"], float(change.get("value", 5.0)))
                for sig in scenario_config.get("signal_changes", []):
                    if t == 0:
                        traci.trafficlight.setPhase(sig["traffic_light_id"], int(sig["phase_index"]))
                        traci.trafficlight.setPhaseDuration(sig["traffic_light_id"], int(sig["new_duration_sec"]))
                traci.simulationStep()
            return {
                "status": "completed",
                "arrived": traci.simulation.getArrivedNumber(),
                "departed": traci.simulation.getDepartedNumber(),
                "teleports_starting": traci.simulation.getStartingTeleportNumber(),
            }
        finally:
            traci.close()
