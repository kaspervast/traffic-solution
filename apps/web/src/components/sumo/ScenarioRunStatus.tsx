import type { RunResult } from "./types";

function StatusPill({ status }: { status: RunResult["status"] }) {
  const colors: Record<RunResult["status"], string> = {
    queued: "#64748b",
    preparing: "#64748b",
    running: "#0ea5e9",
    completed: "#16a34a",
    failed: "#dc2626",
    cancelled: "#94a3b8",
  };
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase text-white"
      style={{ backgroundColor: colors[status] }}
    >
      {status}
    </span>
  );
}

export function ScenarioRunStatus({ label, run }: { label: string; run: RunResult | null }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase text-slate-400">{label}</h3>
        {run && <StatusPill status={run.status} />}
      </div>
      {!run ? (
        <p className="mt-1 text-xs text-slate-500">Not run yet.</p>
      ) : (
        <div className="mt-1 text-xs text-slate-300">
          <div>run_id: {run.run_id}</div>
          {run.error && <div className="text-red-400">{run.error}</div>}
          {run.metrics && (
            <ul className="mt-1 space-y-0.5">
              <li>Arrived: {run.metrics.total_arrived ?? "n/a"}</li>
              <li>
                Avg travel time:{" "}
                {(run.metrics.average_duration_sec ?? run.metrics.average_travel_time_sec)?.toFixed?.(1) ?? "n/a"}{" "}
                s
              </li>
              <li>Avg time loss: {run.metrics.average_time_loss_sec?.toFixed?.(1) ?? "n/a"} s</li>
              <li>Teleports: {run.metrics.total_teleports ?? 0}</li>
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
