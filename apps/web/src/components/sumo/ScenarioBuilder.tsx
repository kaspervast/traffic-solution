"use client";

import { useState } from "react";
import type { ScenarioType } from "./types";

interface ScenarioBuilderProps {
  selectedEdgeId: string | null;
  onRunBaseline: () => void;
  onRunScenario: (config: {
    name: string;
    scenarioType: ScenarioType;
    startSecond: number;
    endSecond: number;
    demandFactor: number;
  }) => void;
  isRunningBaseline: boolean;
  isRunningScenario: boolean;
}

const SCENARIO_TYPES: ScenarioType[] = [
  "road_closure",
  "lane_block",
  "one_way_conversion",
  "signal_timing_change",
  "event_demand_surge",
  "rain_slowdown",
  "combined",
];

export function ScenarioBuilder({
  selectedEdgeId,
  onRunBaseline,
  onRunScenario,
  isRunningBaseline,
  isRunningScenario,
}: ScenarioBuilderProps) {
  const [name, setName] = useState("Evening peak road closure");
  const [scenarioType, setScenarioType] = useState<ScenarioType>("road_closure");
  const [startSecond, setStartSecond] = useState(0);
  const [endSecond, setEndSecond] = useState(3600);
  const [demandFactor, setDemandFactor] = useState(1.0);

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-200">Scenario builder</h3>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <label className="col-span-2">
          Scenario name
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
          />
        </label>
        <label>
          Scenario type
          <select
            value={scenarioType}
            onChange={(e) => setScenarioType(e.target.value as ScenarioType)}
            className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
          >
            {SCENARIO_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          Selected SUMO edge
          <input
            readOnly
            value={selectedEdgeId ?? "click an edge on the map"}
            className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-400"
          />
        </label>
        <label>
          Start second
          <input
            type="number"
            value={startSecond}
            onChange={(e) => setStartSecond(Number(e.target.value))}
            className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
          />
        </label>
        <label>
          End second
          <input
            type="number"
            value={endSecond}
            onChange={(e) => setEndSecond(Number(e.target.value))}
            className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
          />
        </label>
        <label className="col-span-2">
          Demand factor ({demandFactor.toFixed(1)}x)
          <input
            type="range"
            min={0.1}
            max={5}
            step={0.1}
            value={demandFactor}
            onChange={(e) => setDemandFactor(Number(e.target.value))}
            className="mt-0.5 w-full"
          />
        </label>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          onClick={onRunBaseline}
          disabled={isRunningBaseline}
          className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:border-slate-400 disabled:opacity-50"
        >
          {isRunningBaseline ? "Running baseline…" : "Run baseline"}
        </button>
        <button
          onClick={() =>
            onRunScenario({ name, scenarioType, startSecond, endSecond, demandFactor })
          }
          disabled={!selectedEdgeId || isRunningScenario}
          className="rounded bg-orange-700 px-3 py-1.5 text-xs text-white hover:bg-orange-600 disabled:opacity-50"
        >
          {isRunningScenario ? "Running scenario…" : "Run scenario"}
        </button>
      </div>
    </div>
  );
}
