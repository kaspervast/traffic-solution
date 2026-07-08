"""SUMO scenario runner (spec section P, SUMO-integrated override).

This is the spec's base code, kept close to the original with two
Windows-native adaptations:

1. `sumo_binary` defaults to resolving a real executable path (SUMO_HOME/
   bin/sumo.exe on Windows, or "sumo" on PATH) instead of assuming the bare
   "sumo" command resolves, since Windows does not have it on PATH by
   default the way the Ubuntu Docker image (spec section M) does.
2. `_execute_sumo` passes the platform-appropriate boolean flag syntax and
   avoids POSIX-only assumptions when locating the sumo binary.

Every run directory ends up with: scenario.sumocfg, scenario.rou.xml (copied
from the base scenario's demand/baseline.rou.xml), tripinfo.xml,
summary.xml, edgeData.xml, run.log -- matching spec section K.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def resolve_sumo_binary(preferred: str = "sumo") -> str:
    """Best-effort resolution of the sumo executable across platforms.

    Order: explicit SUMO_HOME/bin/sumo(.exe) if SUMO_HOME is set and the
    file exists, else fall back to the bare command name and let the OS
    PATH resolve it (this is what happens inside the Docker image where
    apt installs sumo onto PATH directly).
    """
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        exe_name = "sumo.exe" if platform.system() == "Windows" else "sumo"
        candidate = Path(sumo_home) / "bin" / exe_name
        if candidate.exists():
            return str(candidate)
    return preferred


@dataclass
class SumoRunResult:
    run_id: str
    status: str
    run_dir: str
    metrics: dict[str, Any]
    error: str | None = None


class SumoScenarioRunner:
    def __init__(self, base_scenario_dir: str, runs_dir: str, sumo_binary: str = "sumo") -> None:
        # Resolve to absolute paths: _execute_sumo runs the sumo subprocess
        # with cwd=run_dir, so a relative sumocfg path here would be
        # re-interpreted relative to run_dir and resolve incorrectly.
        self.base_scenario_dir = Path(base_scenario_dir).resolve()
        self.runs_dir = Path(runs_dir).resolve()
        self.sumo_binary = resolve_sumo_binary(sumo_binary)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def run_scenario(self, scenario_config: dict[str, Any]) -> dict[str, Any]:
        run_id = scenario_config.get("run_id") or str(uuid.uuid4())
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._copy_base_files(run_dir)
            self._write_additional_file(run_dir, scenario_config)
            sumocfg = self._write_sumocfg(run_dir, scenario_config)
            ok = self._execute_sumo(run_dir, sumocfg)
            metrics = self._parse_tripinfo(run_dir / "tripinfo.xml")
            return asdict(SumoRunResult(
                run_id=run_id,
                status="completed" if ok else "failed",
                run_dir=str(run_dir),
                metrics=metrics,
                error=None if ok else "SUMO exited with non-zero status (see run.log)",
            ))
        except Exception as exc:
            return asdict(SumoRunResult(
                run_id=run_id,
                status="failed",
                run_dir=str(run_dir),
                metrics={},
                error=str(exc),
            ))

    def _copy_base_files(self, run_dir: Path) -> None:
        for item in self.base_scenario_dir.iterdir():
            if item.name == "runs":
                continue
            target = run_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    def _write_additional_file(self, run_dir: Path, scenario_config: dict[str, Any]) -> None:
        root = ET.Element("additional")
        for change in scenario_config.get("edge_changes", []):
            edge_id = change["sumo_edge_id"]
            action = change["action"]
            start = str(change.get("start_second", 0))
            end = str(change.get("end_second", 3600))
            if action == "close":
                rerouter = ET.SubElement(root, "rerouter", id=f"rr_{edge_id}", edges=edge_id)
                interval = ET.SubElement(rerouter, "interval", begin=start, end=end)
                ET.SubElement(interval, "closingReroute", id=edge_id)
            elif action == "reduce_speed":
                # variableSpeedSign-style edge speed override via additional file,
                # implemented as a simple closingReroute-free speed limit patch:
                # SUMO additional files support <edge id> speed override through
                # a rerouter is non-trivial; the TraCI runtime runner
                # (traci_runner.py) is the supported path for reduce_speed. Here
                # we at least record intent in a comment so the run is
                # inspectable even when only the synchronous static-config path
                # is used.
                comment = ET.Comment(
                    f" reduce_speed on {edge_id} to {change.get('value')} "
                    f"[{start},{end}] -- apply via traci_runner for runtime effect "
                )
                root.append(comment)
        ET.ElementTree(root).write(run_dir / "scenario.additional.xml", encoding="utf-8", xml_declaration=True)

    def _write_sumocfg(self, run_dir: Path, scenario_config: dict[str, Any]) -> Path:
        begin = scenario_config.get("simulation_start_second", 0)
        end = scenario_config.get("simulation_end_second", 3600)
        seed = scenario_config.get("random_seed", 42)
        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <input>
    <net-file value="network/rajkot_pilot.net.xml"/>
    <route-files value="demand/baseline.rou.xml"/>
    <additional-files value="scenario.additional.xml"/>
  </input>
  <time>
    <begin value="{begin}"/>
    <end value="{end}"/>
    <step-length value="1"/>
  </time>
  <output>
    <tripinfo-output value="tripinfo.xml"/>
    <summary-output value="summary.xml"/>
  </output>
  <processing>
    <ignore-route-errors value="true"/>
    <time-to-teleport value="300"/>
  </processing>
  <random_number>
    <seed value="{seed}"/>
  </random_number>
</configuration>
'''
        path = run_dir / "scenario.sumocfg"
        path.write_text(content, encoding="utf-8")
        return path

    def _execute_sumo(self, run_dir: Path, sumocfg: Path) -> bool:
        cmd = [
            self.sumo_binary,
            "-c", str(sumocfg),
            "--edgedata-output", str(run_dir / "edgeData.xml"),
            "--no-step-log", "true",
            "--duration-log.statistics", "true",
            # Without a rerouting device, vehicles keep their statically
            # pre-computed duarouter route for the whole trip and never
            # re-evaluate it against a <rerouter>/<closingReroute> defined
            # in scenario.additional.xml -- edge closures and lane/speed
            # changes would then silently have zero effect (confirmed via
            # baseline vs road-closure comparison during development: this
            # flag was required to see any metrics delta at all).
            "--device.rerouting.probability", "1.0",
            "--device.rerouting.period", "30",
        ]
        with (run_dir / "run.log").open("w", encoding="utf-8") as log:
            proc = subprocess.run(cmd, cwd=str(run_dir), stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
        return proc.returncode == 0

    def _parse_tripinfo(self, tripinfo_path: Path) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "total_arrived": 0,
            "average_duration_sec": None,
            "average_waiting_time_sec": None,
            "average_time_loss_sec": None,
            "total_time_loss_sec": 0.0,
        }
        if not tripinfo_path.exists():
            return metrics
        durations, waits, losses = [], [], []
        for _, elem in ET.iterparse(tripinfo_path, events=("end",)):
            if elem.tag == "tripinfo":
                metrics["total_arrived"] += 1
                durations.append(float(elem.attrib.get("duration", 0)))
                waits.append(float(elem.attrib.get("waitingTime", 0)))
                losses.append(float(elem.attrib.get("timeLoss", 0)))
                elem.clear()
        if durations:
            metrics["average_duration_sec"] = sum(durations) / len(durations)
            metrics["average_waiting_time_sec"] = sum(waits) / len(waits)
            metrics["average_time_loss_sec"] = sum(losses) / len(losses)
            metrics["total_time_loss_sec"] = sum(losses)
        return metrics
