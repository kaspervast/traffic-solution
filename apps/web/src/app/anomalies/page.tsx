"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api, ApiError } from "@/lib/api";
import { useAnomaliesOpen } from "@/lib/hooks";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { SEVERITY_COLORS, type Anomaly, type Severity } from "@/types";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

export default function AnomaliesPage() {
  const [severity, setSeverity] = useState<Severity | undefined>(undefined);
  const anomaliesQuery = useAnomaliesOpen(severity);
  const queryClient = useQueryClient();

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/api/anomalies/${id}/status`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["anomalies-open"] }),
  });

  const timeline = useMemo(() => {
    const anomalies = anomaliesQuery.data ?? [];
    const buckets = new Map<string, number>();
    anomalies.forEach((a) => {
      const bucket = new Date(a.detected_at);
      bucket.setMinutes(0, 0, 0);
      const key = bucket.toISOString();
      buckets.set(key, (buckets.get(key) ?? 0) + 1);
    });
    return Array.from(buckets.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([time, count]) => ({ time: new Date(time).toLocaleString(), count }));
  }, [anomaliesQuery.data]);

  return (
    <div className="p-4">
      <h1 className="mb-4 text-lg font-semibold text-slate-100">Anomaly Monitor</h1>

      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setSeverity(undefined)}
          className={`rounded px-3 py-1 text-xs ${!severity ? "bg-slate-700 text-white" : "border border-slate-700 text-slate-300"}`}
        >
          All
        </button>
        {SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setSeverity(s)}
            className="rounded px-3 py-1 text-xs"
            style={{
              backgroundColor: severity === s ? SEVERITY_COLORS[s] : "transparent",
              border: `1px solid ${SEVERITY_COLORS[s]}`,
              color: severity === s ? "#0f172a" : SEVERITY_COLORS[s],
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {anomaliesQuery.isError && (
        <ErrorNotice
          message={
            anomaliesQuery.error instanceof ApiError
              ? `Could not load anomalies: ${anomaliesQuery.error.message}`
              : "Could not reach the API."
          }
        />
      )}

      <div className="mb-6 h-48 rounded border border-slate-800 bg-slate-900 p-2">
        {timeline.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            No anomaly timeline data yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
              <Line type="monotone" dataKey="count" stroke="#38bdf8" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs uppercase text-slate-400">
            <tr>
              <th className="p-2">Detected</th>
              <th className="p-2">Severity</th>
              <th className="p-2">Speed (obs / free-flow)</th>
              <th className="p-2">Delay (s)</th>
              <th className="p-2">Status</th>
              <th className="p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(anomaliesQuery.data ?? []).map((a: Anomaly) => (
              <tr key={a.id} className="border-t border-slate-800">
                <td className="p-2 text-xs text-slate-400">{new Date(a.detected_at).toLocaleString()}</td>
                <td className="p-2">
                  <span className="text-xs font-semibold" style={{ color: SEVERITY_COLORS[a.severity] }}>
                    {a.severity}
                  </span>
                </td>
                <td className="p-2 text-xs">
                  {a.observed_speed_kmph ?? "?"} / {a.baseline_speed_kmph ?? "?"} km/h
                </td>
                <td className="p-2 text-xs">{a.delay_sec ?? "?"}</td>
                <td className="p-2 text-xs">{a.status}</td>
                <td className="p-2">
                  <div className="flex gap-1">
                    <button
                      onClick={() => statusMutation.mutate({ id: a.id, status: "acknowledged" })}
                      className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300 hover:border-slate-500"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={() => statusMutation.mutate({ id: a.id, status: "resolved" })}
                      className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300 hover:border-slate-500"
                    >
                      Resolve
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {(anomaliesQuery.data ?? []).length === 0 && !anomaliesQuery.isError && (
              <tr>
                <td colSpan={6} className="p-4 text-center text-xs text-slate-500">
                  No open anomalies.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
