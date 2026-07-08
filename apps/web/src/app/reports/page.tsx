"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, API_BASE_URL } from "@/lib/api";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PilotScopeWarning } from "@/components/ui/WarningBanner";

interface DailyReport {
  date: string;
  total_anomalies: number;
  severity_counts: { critical: number; high: number; medium: number; low: number };
  worst_locations: {
    probe_point_name: string | null;
    anomaly_count: number;
    avg_speed_ratio: number | null;
    max_delay_sec: number | null;
  }[];
  peak_windows: { window_start: string; window_end: string; anomaly_count: number }[];
  incident_summary: { total_incidents: number; by_category: Record<string, number> };
  is_seed_demo_data: boolean;
  generated_at: string;
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const [date, setDate] = useState(todayISO());

  const reportQuery = useQuery({
    queryKey: ["daily-report", date],
    queryFn: () => api.get<DailyReport>(`/api/reports/daily?date=${date}`),
  });

  return (
    <div className="p-4">
      <PilotScopeWarning />
      <div className="mt-4 mb-4 flex items-end gap-3">
        <div>
          <label className="mb-1 block text-xs text-slate-400">Report date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-100"
          />
        </div>
        <a
          href={`${API_BASE_URL}/api/reports/daily.csv?date=${date}`}
          className="rounded bg-sky-700 px-3 py-1.5 text-sm text-white hover:bg-sky-600"
        >
          Export CSV
        </a>
        <span className="rounded border border-slate-700 px-3 py-1.5 text-sm text-slate-500">
          Export PDF (not implemented in MVP -- TODO)
        </span>
      </div>

      {reportQuery.isError && (
        <ErrorNotice
          message={
            reportQuery.error instanceof ApiError ? reportQuery.error.message : "Could not load report."
          }
        />
      )}

      {reportQuery.data && (
        <div className="space-y-4">
          {reportQuery.data.is_seed_demo_data && (
            <div className="rounded border border-purple-700 bg-purple-950/40 p-2 text-xs text-purple-200">
              This report is built from seed/demo data, not live observations.
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatCard label="Total anomalies" value={reportQuery.data.total_anomalies} />
            <StatCard label="Critical" value={reportQuery.data.severity_counts.critical} accent="#dc2626" />
            <StatCard label="High" value={reportQuery.data.severity_counts.high} accent="#ea580c" />
            <StatCard label="Medium" value={reportQuery.data.severity_counts.medium} accent="#d97706" />
            <StatCard label="Low" value={reportQuery.data.severity_counts.low} accent="#65a30d" />
          </div>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-slate-200">Worst 5 locations</h2>
            {reportQuery.data.worst_locations.length === 0 ? (
              <p className="text-xs text-slate-500">No anomalies recorded for this date.</p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="p-1">Probe point</th>
                    <th className="p-1">Anomaly count</th>
                    <th className="p-1">Avg speed ratio</th>
                    <th className="p-1">Max delay (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {reportQuery.data.worst_locations.map((loc, i) => (
                    <tr key={i} className="border-t border-slate-800">
                      <td className="p-1">{loc.probe_point_name ?? "Unknown"}</td>
                      <td className="p-1">{loc.anomaly_count}</td>
                      <td className="p-1">{loc.avg_speed_ratio ?? "n/a"}</td>
                      <td className="p-1">{loc.max_delay_sec ?? "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-slate-200">Peak congestion windows</h2>
            {reportQuery.data.peak_windows.length === 0 ? (
              <p className="text-xs text-slate-500">No peak windows identified.</p>
            ) : (
              <ul className="text-sm text-slate-300">
                {reportQuery.data.peak_windows.map((w, i) => (
                  <li key={i}>
                    {new Date(w.window_start).toLocaleTimeString()} - {new Date(w.window_end).toLocaleTimeString()}:{" "}
                    {w.anomaly_count} anomalies
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-slate-200">Incident summary</h2>
            <p className="text-sm text-slate-300">
              {reportQuery.data.incident_summary.total_incidents} incidents first seen on {date}.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <div className="text-2xl font-semibold" style={{ color: accent ?? "#e2e8f0" }}>
        {value}
      </div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
