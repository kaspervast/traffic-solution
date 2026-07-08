"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAOI, useAnomaliesOpen, useIncidentsLive, useProbePoints, useTrafficLive } from "@/lib/hooks";
import { PilotScopeWarning } from "@/components/ui/WarningBanner";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import type { Anomaly, CommandAnswer, IngestionRunResult } from "@/types";
import { SEVERITY_COLORS } from "@/types";

const LiveMap = dynamic(() => import("@/components/map/LiveMap").then((m) => m.LiveMap), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-slate-500">Loading map…</div>,
});

const SUGGESTED_QUESTIONS = [
  "What is causing delay in this area right now?",
  "Summarize yesterday evening peak congestion.",
  "Which road segment has repeated bottlenecks?",
  "Draft an advisory for citizens.",
  "What should police deployment focus on for the next 2 hours?",
];

function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  return (
    <div
      className="rounded border border-slate-700 bg-slate-900 p-3"
      style={{ borderLeftColor: SEVERITY_COLORS[anomaly.severity], borderLeftWidth: 4 }}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase" style={{ color: SEVERITY_COLORS[anomaly.severity] }}>
          {anomaly.severity}
        </span>
        <span className="text-[10px] text-slate-500">{new Date(anomaly.detected_at).toLocaleTimeString()}</span>
      </div>
      <div className="mt-1 text-sm text-slate-200">
        {anomaly.observed_speed_kmph ?? "?"} km/h vs free-flow {anomaly.baseline_speed_kmph ?? "?"} km/h
      </div>
      <div className="text-xs text-slate-400">delay {anomaly.delay_sec ?? "?"}s · status: {anomaly.status}</div>
    </div>
  );
}

export default function CommandCenterPage() {
  const aoiQuery = useAOI();
  const probesQuery = useProbePoints();
  const trafficQuery = useTrafficLive();
  const incidentsQuery = useIncidentsLive();
  const anomaliesQuery = useAnomaliesOpen();
  const queryClient = useQueryClient();

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<CommandAnswer | null>(null);

  const askMutation = useMutation({
    mutationFn: (q: string) => api.post<CommandAnswer>("/api/ai/command", { question: q }),
    onSuccess: (data) => setAnswer(data),
  });

  const ingestMutation = useMutation({
    mutationFn: () => api.post<IngestionRunResult>("/api/ingestion/run-now"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["traffic-live"] });
      queryClient.invalidateQueries({ queryKey: ["incidents-live"] });
      queryClient.invalidateQueries({ queryKey: ["anomalies-open"] });
    },
  });

  const observationsByProbe = useMemo(() => {
    const map: Record<string, (typeof trafficQuery)["data"] extends (infer U)[] | undefined ? U : never> = {};
    (trafficQuery.data ?? []).forEach((o) => {
      if (o.probe_point_id) map[o.probe_point_id] = o as never;
    });
    return map;
  }, [trafficQuery.data]);

  const anomaliesByProbe = useMemo(() => {
    const map: Record<string, Anomaly> = {};
    (anomaliesQuery.data ?? []).forEach((a) => {
      if (a.probe_point_id) map[a.probe_point_id] = a;
    });
    return map;
  }, [anomaliesQuery.data]);

  return (
    <div className="flex h-[calc(100vh-49px)] flex-col">
      <PilotScopeWarning />
      <div className="grid flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[1.3fr_1fr]">
        <div className="relative h-[45vh] lg:h-auto">
          {aoiQuery.isError && (
            <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-slate-950/90 p-4">
              <ErrorNotice
                message={
                  aoiQuery.error instanceof ApiError
                    ? `Could not load AOI: ${aoiQuery.error.message}. Run scripts/seed_aoi.py once the database migration has been applied.`
                    : "Could not reach the API."
                }
              />
            </div>
          )}
          <LiveMap
            aoi={aoiQuery.data}
            probePoints={probesQuery.data ?? []}
            observationsByProbe={observationsByProbe}
            incidents={incidentsQuery.data ?? []}
            anomaliesByProbe={anomaliesByProbe}
          />
        </div>

        <div className="flex flex-col gap-4 overflow-y-auto border-l border-slate-800 p-4">
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">Active Anomalies</h2>
              <button
                onClick={() => ingestMutation.mutate()}
                disabled={ingestMutation.isPending}
                className="rounded bg-sky-700 px-2 py-1 text-xs text-white hover:bg-sky-600 disabled:opacity-50"
              >
                {ingestMutation.isPending ? "Running…" : "Run ingestion now"}
              </button>
            </div>
            {ingestMutation.isError && (
              <ErrorNotice
                message={
                  ingestMutation.error instanceof ApiError
                    ? ingestMutation.error.message
                    : "Ingestion run failed."
                }
              />
            )}
            <div className="flex flex-col gap-2">
              {(anomaliesQuery.data ?? []).length === 0 ? (
                <div className="text-xs text-slate-500">No open anomalies.</div>
              ) : (
                anomaliesQuery.data!.map((a) => <AnomalyCard key={a.id} anomaly={a} />)
              )}
            </div>
          </section>

          <section className="border-t border-slate-800 pt-4">
            <h2 className="mb-2 text-sm font-semibold text-slate-200">Command Center</h2>
            <div className="mb-2 flex flex-wrap gap-1">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="rounded-full border border-slate-700 px-2 py-1 text-[11px] text-slate-300 hover:border-slate-500"
                >
                  {q}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (question.trim()) askMutation.mutate(question.trim());
              }}
              className="flex gap-2"
            >
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about current traffic conditions…"
                className="flex-1 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={askMutation.isPending}
                className="rounded bg-emerald-700 px-3 py-2 text-sm text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {askMutation.isPending ? "Asking…" : "Ask"}
              </button>
            </form>

            {askMutation.isError && (
              <div className="mt-2">
                <ErrorNotice
                  message={
                    askMutation.error instanceof ApiError ? askMutation.error.message : "Command failed."
                  }
                />
              </div>
            )}

            {answer && (
              <div className="mt-3 rounded border border-slate-700 bg-slate-900 p-3 text-sm">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs uppercase text-slate-500">intent: {answer.intent}</span>
                  <span className="text-xs text-slate-400">confidence: {Math.round(answer.confidence * 100)}%</span>
                </div>
                <p className="whitespace-pre-wrap text-slate-100">{answer.answer}</p>
                {answer.evidence.length > 0 && (
                  <table className="mt-2 w-full text-left text-xs text-slate-400">
                    <tbody>
                      {answer.evidence.map((e, i) => (
                        <tr key={i} className="border-t border-slate-800">
                          <td className="py-1 pr-2">{e.label}</td>
                          <td className="py-1 pr-2">{e.value}</td>
                          <td className="py-1 text-slate-500">{e.source}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {answer.assumptions.length > 0 && (
                  <div className="mt-2 text-xs text-amber-300">
                    Assumptions: {answer.assumptions.join("; ")}
                  </div>
                )}
                {answer.missing_data.length > 0 && (
                  <div className="mt-1 text-xs text-amber-300">
                    Missing data: {answer.missing_data.join("; ")}
                  </div>
                )}
                {answer.suggested_advisory && (
                  <div className="mt-3 flex items-start justify-between gap-2 rounded bg-slate-800 p-2">
                    <p className="text-xs text-slate-200">{answer.suggested_advisory}</p>
                    <button
                      onClick={() => navigator.clipboard.writeText(answer.suggested_advisory ?? "")}
                      className="shrink-0 rounded border border-slate-600 px-2 py-1 text-[10px] text-slate-300 hover:border-slate-400"
                    >
                      Copy advisory
                    </button>
                  </div>
                )}
                <div className="mt-2 text-[10px] text-slate-500">
                  AI drafts require human review before any public advisory or alert is sent.
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
