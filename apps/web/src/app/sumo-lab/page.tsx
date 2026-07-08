"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAOI } from "@/lib/hooks";
import { SumoEstimateWarning } from "@/components/ui/WarningBanner";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { ScenarioBuilder } from "@/components/sumo/ScenarioBuilder";
import { ScenarioRunStatus } from "@/components/sumo/ScenarioRunStatus";
import { ScenarioComparison } from "@/components/sumo/ScenarioComparison";
import { EdgeImpactTable } from "@/components/sumo/EdgeImpactTable";
import type { RunResult } from "@/components/sumo/types";
import type { ScenarioComparison as ScenarioComparisonType, SumoEdgeOut } from "@/types";

const SumoMapLayer = dynamic(() => import("@/components/sumo/SumoMapLayer").then((m) => m.SumoMapLayer), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-slate-500">Loading map…</div>,
});

interface SumoNetworkSummary {
  id: string;
  name: string;
  net_file_path: string;
}

export default function SumoLabPage() {
  const aoiQuery = useAOI();
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [baselineRun, setBaselineRun] = useState<RunResult | null>(null);
  const [scenarioRun, setScenarioRun] = useState<RunResult | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparisonType | null>(null);
  const [geminiSummary, setGeminiSummary] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const networksQuery = useQuery({
    queryKey: ["sumo-networks"],
    queryFn: () => api.get<SumoNetworkSummary[]>("/api/sumo/networks"),
    retry: false,
  });
  const networkId = networksQuery.data?.[0]?.id;

  const edgesQuery = useQuery({
    queryKey: ["sumo-edges", networkId],
    queryFn: () => api.get<SumoEdgeOut[]>(`/api/sumo/networks/${networkId}/edges`),
    enabled: !!networkId,
    retry: false,
  });

  const baselineMutation = useMutation({
    mutationFn: async () => {
      setRunError(null);
      // Baseline runs use the simulation service directly with an empty
      // scenario config (no edge/signal/demand changes) -- this mirrors
      // exactly what services/simulation/app/scenario_runner.py does for
      // scenario_closure_final's baseline comparison during development.
      return api.post<RunResult>("/api/sumo/scenarios", {
        name: "Baseline",
        scenario_type: "road_closure",
        aoi_id: aoiQuery.data?.id ?? "",
        network_id: networkId ?? "",
        edge_changes: [],
      });
    },
    onError: (err) => setRunError(err instanceof ApiError ? err.message : "Baseline run failed"),
  });

  const scenarioMutation = useMutation({
    mutationFn: async (config: {
      name: string;
      scenarioType: string;
      startSecond: number;
      endSecond: number;
      demandFactor: number;
    }) => {
      setRunError(null);
      if (!selectedEdgeId) throw new Error("Select an edge first");
      const scenario = await api.post<{ id: string }>("/api/sumo/scenarios", {
        name: config.name,
        scenario_type: config.scenarioType,
        aoi_id: aoiQuery.data?.id ?? "",
        network_id: networkId ?? "",
        simulation_start_second: config.startSecond,
        simulation_end_second: config.endSecond,
        edge_changes: [
          { sumo_edge_id: selectedEdgeId, action: "close", start_second: config.startSecond, end_second: config.endSecond },
        ],
      });
      return api.post<RunResult>(`/api/sumo/scenarios/${scenario.id}/run`);
    },
    onSuccess: (data) => setScenarioRun(data),
    onError: (err) => setRunError(err instanceof ApiError ? err.message : "Scenario run failed"),
  });

  const summarizeMutation = useMutation({
    mutationFn: async () => {
      if (!scenarioRun || !baselineRun) throw new Error("Run baseline and scenario first");
      return api.post<{ comparison: ScenarioComparisonType; gemini_summary: { summary: string } }>(
        `/api/sumo/runs/${scenarioRun.run_id}/summarize-with-gemini?baseline_run_id=${baselineRun.run_id}`,
      );
    },
    onSuccess: (data) => {
      setComparison(data.comparison);
      setGeminiSummary(data.gemini_summary.summary);
    },
  });

  return (
    <div className="flex h-[calc(100vh-49px)] flex-col">
      <SumoEstimateWarning />
      <div className="grid flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[1.3fr_1fr]">
        <div className="relative h-[45vh] lg:h-auto">
          {networksQuery.isError || !networkId ? (
            <div className="flex h-full items-center justify-center p-4">
              <ErrorNotice message="No SUMO network registered in the database yet. Run scripts/import_sumo_edges.py once the migration has been applied (a real rajkot_pilot.net.xml with 1667 routable edges already exists on disk -- see services/simulation/scenarios/rajkot_pilot/network/)." />
            </div>
          ) : aoiQuery.data ? (
            <SumoMapLayer
              centerLat={aoiQuery.data.center_lat}
              centerLon={aoiQuery.data.center_lon}
              radiusM={aoiQuery.data.radius_m}
              edges={edgesQuery.data ?? []}
              selectedEdgeId={selectedEdgeId}
              onSelectEdge={setSelectedEdgeId}
            />
          ) : null}
        </div>

        <div className="flex flex-col gap-3 overflow-y-auto border-l border-slate-800 p-4">
          <ScenarioBuilder
            selectedEdgeId={selectedEdgeId}
            onRunBaseline={() => baselineMutation.mutate()}
            onRunScenario={(config) => scenarioMutation.mutate(config)}
            isRunningBaseline={baselineMutation.isPending}
            isRunningScenario={scenarioMutation.isPending}
          />

          {runError && <ErrorNotice message={runError} />}

          <ScenarioRunStatus label="Baseline run" run={baselineRun} />
          <ScenarioRunStatus label="Scenario run" run={scenarioRun} />

          {baselineRun && scenarioRun && (
            <button
              onClick={() => summarizeMutation.mutate()}
              disabled={summarizeMutation.isPending}
              className="rounded bg-purple-700 px-3 py-1.5 text-xs text-white hover:bg-purple-600 disabled:opacity-50"
            >
              {summarizeMutation.isPending ? "Comparing…" : "Compare + summarize with Gemini"}
            </button>
          )}

          {comparison && (
            <div className="space-y-2 border-t border-slate-800 pt-3">
              <h3 className="text-sm font-semibold text-slate-200">Comparison</h3>
              <ScenarioComparison comparison={comparison} />
              <EdgeImpactTable edgeImpacts={comparison.edge_impacts} />
            </div>
          )}

          {geminiSummary && (
            <div className="rounded border border-purple-800 bg-purple-950/30 p-3 text-xs text-purple-100">
              <div className="mb-1 font-semibold uppercase text-purple-300">Gemini result summary</div>
              {geminiSummary}
              <div className="mt-2 text-[10px] text-purple-300">
                Planning estimate only. Requires engineering/field validation before any operational change.
              </div>
            </div>
          )}

          <div className="mt-2 text-[10px] text-slate-500">
            Export: use /api/sumo/runs/&#123;run_id&#125;/files for run artifacts (CSV/PDF scenario export is a
            follow-up TODO for this MVP).
          </div>
        </div>
      </div>
    </div>
  );
}
