"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { ScenarioRunStatus } from "@/components/sumo/ScenarioRunStatus";
import type { RunResult, ScenarioDraft } from "./types";

interface AiScenarioChatProps {
  selectedEdgeId: string | null;
  networkId: string | undefined;
  aoiId: string | undefined;
}

const EXAMPLE_PROMPTS = [
  "Close this junction for 30 minutes during evening peak",
  "Reduce this road to one lane for the whole simulation",
  "Simulate a demand surge here for a local event",
];

function describeEdgeChange(c: ScenarioDraft["edge_changes"][number]): string {
  const window = `[${c.start_second}s - ${c.end_second}s]`;
  switch (c.action) {
    case "close":
      return `Close edge ${c.sumo_edge_id} ${window}`;
    case "reduce_speed":
      return `Reduce speed on edge ${c.sumo_edge_id} to ${c.value ?? "?"} ${window}`;
    case "reduce_lanes":
      return `Reduce lanes on edge ${c.sumo_edge_id} to ${c.value ?? "?"} ${window}`;
    case "reverse_direction":
      return `Reverse direction on edge ${c.sumo_edge_id} ${window}`;
    case "capacity_factor":
      return `Apply capacity factor ${c.value ?? "?"} to edge ${c.sumo_edge_id} ${window}`;
    default:
      return `${c.action} on edge ${c.sumo_edge_id} ${window}`;
  }
}

function describeSignalChange(c: ScenarioDraft["signal_changes"][number]): string {
  return `Traffic light ${c.traffic_light_id}, phase ${c.phase_index} -> ${c.new_duration_sec}s duration`;
}

function describeDemandChange(c: ScenarioDraft["demand_changes"][number]): string {
  const window = `[${c.start_second}s - ${c.end_second}s]`;
  return `${c.demand_type.replace(/_/g, " ")}, factor ${c.factor}x ${window}`;
}

export function AiScenarioChat({ selectedEdgeId, networkId, aoiId }: AiScenarioChatProps) {
  const [requestText, setRequestText] = useState("");
  const [draft, setDraft] = useState<ScenarioDraft | null>(null);
  const [contextUsed, setContextUsed] = useState<unknown>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [savedScenarioId, setSavedScenarioId] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<RunResult | null>(null);

  const canDraft = !!selectedEdgeId && !!networkId && !!aoiId;

  const draftMutation = useMutation({
    mutationFn: async () => {
      if (!canDraft) throw new Error("Select a SUMO edge on the map first");
      return api.post<{ draft: ScenarioDraft; context_used: unknown }>("/api/sumo/scenarios/draft", {
        request_text: requestText,
        sumo_edge_id: selectedEdgeId,
        network_id: networkId,
        aoi_id: aoiId,
      });
    },
    onSuccess: (data) => {
      setDraft(data.draft);
      setContextUsed(data.context_used);
      setSavedScenarioId(null);
      setRunResult(null);
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error("No draft to save");
      const created = await api.post<{ id: string }>("/api/sumo/scenarios", {
        ...draft,
        // Defensive: pin aoi_id/network_id to what the operator actually
        // selected rather than trusting the drafted values verbatim.
        aoi_id: aoiId ?? draft.aoi_id,
        network_id: networkId ?? draft.network_id,
      });
      await api.patch(`/api/sumo/scenarios/${created.id}`, { human_review_status: "approved" });
      return created.id;
    },
    onSuccess: (id) => setSavedScenarioId(id),
  });

  const runMutation = useMutation({
    mutationFn: async () => {
      if (!savedScenarioId) throw new Error("Save the scenario first");
      return api.post<RunResult>(`/api/sumo/scenarios/${savedScenarioId}/run`);
    },
    onSuccess: (data) => setRunResult(data),
  });

  function discard() {
    setDraft(null);
    setContextUsed(null);
    setSavedScenarioId(null);
    setRunResult(null);
    setShowRawJson(false);
  }

  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <h3 className="mb-2 text-sm font-semibold text-slate-200">Ask AI to draft a scenario</h3>

      {!selectedEdgeId && (
        <p className="mb-2 text-xs text-amber-300">Select an edge on the map first, then describe what you want to test.</p>
      )}

      <div className="mb-2 flex flex-wrap gap-1">
        {EXAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => setRequestText(p)}
            className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300 hover:border-slate-500"
          >
            {p}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (requestText.trim()) draftMutation.mutate();
        }}
        className="flex gap-2"
      >
        <input
          value={requestText}
          onChange={(e) => setRequestText(e.target.value)}
          placeholder="e.g. close this junction for 30 minutes during evening peak"
          disabled={!canDraft}
          className="flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100 placeholder:text-slate-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!canDraft || !requestText.trim() || draftMutation.isPending}
          className="rounded bg-purple-700 px-3 py-1.5 text-xs text-white hover:bg-purple-600 disabled:opacity-50"
        >
          {draftMutation.isPending ? "Drafting…" : "Draft"}
        </button>
      </form>

      <div className="mt-1 text-[10px] text-slate-500">
        Single-edge closures often show no measurable effect on this dense grid (short redundant
        alternate paths); a hard closure is more reliable for a visible impact. This is a draft --
        nothing runs until you approve and click "Run now".
      </div>

      {draftMutation.isError && (
        <div className="mt-2">
          <ErrorNotice
            message={draftMutation.error instanceof ApiError ? draftMutation.error.message : "Draft failed."}
          />
        </div>
      )}

      {draft && (
        <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
          <div className="text-xs text-slate-200">
            <div className="font-semibold text-slate-100">{draft.name}</div>
            <div className="text-slate-400">
              Type: {draft.scenario_type} · window {draft.simulation_start_second}s - {draft.simulation_end_second}s ·
              seed {draft.random_seed}
            </div>
            {draft.description && <div className="mt-1 text-slate-300">{draft.description}</div>}
          </div>

          {draft.edge_changes.length > 0 && (
            <ul className="list-inside list-disc text-xs text-slate-300">
              {draft.edge_changes.map((c, i) => (
                <li key={`edge-${i}`}>{describeEdgeChange(c)}</li>
              ))}
            </ul>
          )}
          {draft.signal_changes.length > 0 && (
            <ul className="list-inside list-disc text-xs text-slate-300">
              {draft.signal_changes.map((c, i) => (
                <li key={`signal-${i}`}>{describeSignalChange(c)}</li>
              ))}
            </ul>
          )}
          {draft.demand_changes.length > 0 && (
            <ul className="list-inside list-disc text-xs text-slate-300">
              {draft.demand_changes.map((c, i) => (
                <li key={`demand-${i}`}>{describeDemandChange(c)}</li>
              ))}
            </ul>
          )}
          {draft.edge_changes.length === 0 && draft.signal_changes.length === 0 && draft.demand_changes.length === 0 && (
            <p className="text-xs text-slate-500">No concrete changes drafted -- review before saving.</p>
          )}

          <details className="text-xs text-slate-400">
            <summary
              className="cursor-pointer select-none text-slate-500 hover:text-slate-300"
              onClick={() => setShowRawJson((v) => !v)}
            >
              Raw JSON (draft + grounded context used)
            </summary>
            {showRawJson && (
              <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-950 p-2 text-[10px] text-slate-400">
                {JSON.stringify({ draft, context_used: contextUsed }, null, 2)}
              </pre>
            )}
          </details>

          {!savedScenarioId ? (
            <div className="flex gap-2">
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                className="rounded bg-emerald-700 px-3 py-1.5 text-xs text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {saveMutation.isPending ? "Saving…" : "Approve & save"}
              </button>
              <button
                onClick={discard}
                className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:border-slate-400"
              >
                Discard
              </button>
            </div>
          ) : (
            <button
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
              className="rounded bg-orange-700 px-3 py-1.5 text-xs text-white hover:bg-orange-600 disabled:opacity-50"
            >
              {runMutation.isPending ? "Running…" : "Run now"}
            </button>
          )}

          {saveMutation.isError && (
            <ErrorNotice
              message={saveMutation.error instanceof ApiError ? saveMutation.error.message : "Save/approve failed."}
            />
          )}
          {runMutation.isError && (
            <ErrorNotice
              message={runMutation.error instanceof ApiError ? runMutation.error.message : "Run failed."}
            />
          )}

          {runResult && <ScenarioRunStatus label="AI scenario run" run={runResult} />}
        </div>
      )}
    </div>
  );
}
