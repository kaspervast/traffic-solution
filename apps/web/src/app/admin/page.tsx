"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useProbePoints } from "@/lib/hooks";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import type { IngestionRunResult, Priority } from "@/types";

const EMPTY_FORM = { name: "", lat: "", lon: "", priority: "medium" as Priority, notes: "" };

export default function AdminPage() {
  const probesQuery = useProbePoints();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_FORM);
  const [lastRun, setLastRun] = useState<IngestionRunResult | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/api/probe-points", {
        name: form.name,
        lat: parseFloat(form.lat),
        lon: parseFloat(form.lon),
        priority: form.priority,
        notes: form.notes || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["probe-points"] });
      setForm(EMPTY_FORM);
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch(`/api/probe-points/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["probe-points"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.del(`/api/probe-points/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["probe-points"] }),
  });

  const ingestMutation = useMutation({
    mutationFn: () => api.post<IngestionRunResult>("/api/ingestion/run-now"),
    onSuccess: (data) => setLastRun(data),
  });

  return (
    <div className="p-4">
      <h1 className="mb-4 text-lg font-semibold text-slate-100">Admin</h1>

      <section className="mb-6 rounded border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-200">API polling status</h2>
        <button
          onClick={() => ingestMutation.mutate()}
          disabled={ingestMutation.isPending}
          className="rounded bg-sky-700 px-3 py-1.5 text-sm text-white hover:bg-sky-600 disabled:opacity-50"
        >
          {ingestMutation.isPending ? "Running…" : "Trigger manual ingestion run"}
        </button>
        {ingestMutation.isError && (
          <div className="mt-2">
            <ErrorNotice
              message={ingestMutation.error instanceof ApiError ? ingestMutation.error.message : "Failed."}
            />
          </div>
        )}
        {lastRun && (
          <div className="mt-2 text-xs text-slate-400">
            Last run: {new Date(lastRun.finished_at).toLocaleString()} — polled{" "}
            {lastRun.probe_points_polled} probes, stored {lastRun.flow_observations_stored} observations,{" "}
            {lastRun.incidents_upserted} incidents, {lastRun.anomalies_detected} anomalies detected.
            {lastRun.errors.length > 0 && (
              <div className="mt-1 text-amber-300">{lastRun.errors.length} error(s) during run.</div>
            )}
          </div>
        )}
      </section>

      <section className="mb-6 rounded border border-slate-800 bg-slate-900 p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-200">Add probe point</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          className="grid grid-cols-2 gap-2 sm:grid-cols-5"
        >
          <input
            required
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          />
          <input
            required
            placeholder="Lat"
            value={form.lat}
            onChange={(e) => setForm({ ...form, lat: e.target.value })}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          />
          <input
            required
            placeholder="Lon"
            value={form.lon}
            onChange={(e) => setForm({ ...form, lon: e.target.value })}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          />
          <select
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
          >
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </select>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="rounded bg-emerald-700 px-3 py-1.5 text-sm text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            Add
          </button>
        </form>
        {createMutation.isError && (
          <div className="mt-2">
            <ErrorNotice
              message={createMutation.error instanceof ApiError ? createMutation.error.message : "Failed to create."}
            />
          </div>
        )}
      </section>

      <section className="rounded border border-slate-800">
        <h2 className="border-b border-slate-800 bg-slate-900 p-3 text-sm font-semibold text-slate-200">
          Probe points ({(probesQuery.data ?? []).length})
        </h2>
        {probesQuery.isError && (
          <div className="p-3">
            <ErrorNotice
              message={
                probesQuery.error instanceof ApiError
                  ? `Could not load probe points: ${probesQuery.error.message}`
                  : "Could not reach API."
              }
            />
          </div>
        )}
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="p-2">Name</th>
              <th className="p-2">Lat, Lon</th>
              <th className="p-2">Priority</th>
              <th className="p-2">Polling (s)</th>
              <th className="p-2">Active</th>
              <th className="p-2">Notes</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {(probesQuery.data ?? []).map((p) => (
              <tr key={p.id} className="border-t border-slate-800">
                <td className="p-2">{p.name}</td>
                <td className="p-2 text-xs text-slate-400">
                  {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
                </td>
                <td className="p-2 text-xs">{p.priority}</td>
                <td className="p-2 text-xs">{p.polling_interval_seconds}</td>
                <td className="p-2">
                  <button
                    onClick={() => toggleActiveMutation.mutate({ id: p.id, is_active: !p.is_active })}
                    className={`rounded px-2 py-0.5 text-[10px] ${p.is_active ? "bg-emerald-800 text-emerald-200" : "bg-slate-800 text-slate-400"}`}
                  >
                    {p.is_active ? "active" : "inactive"}
                  </button>
                </td>
                <td className="max-w-xs truncate p-2 text-xs text-slate-400" title={p.notes ?? ""}>
                  {p.notes ?? ""}
                </td>
                <td className="p-2">
                  <button
                    onClick={() => deleteMutation.mutate(p.id)}
                    className="rounded border border-red-800 px-2 py-1 text-[10px] text-red-300 hover:bg-red-950"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-6 rounded border border-slate-800 bg-slate-900 p-4 text-xs text-slate-500">
        Local events and alert channel management are stored in the database (
        <code>local_events</code>, <code>alert_channels</code> tables) but do not yet have a dedicated
        admin UI in this MVP -- use the API directly or extend this page. Tracked as a follow-up.
      </section>
    </div>
  );
}
