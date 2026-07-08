import type { ScenarioComparison as ScenarioComparisonType } from "@/types";

function DeltaCard({ label, value, unit = "%" }: { label: string; value: number | null; unit?: string }) {
  const color = value == null ? "#94a3b8" : value > 0 ? "#dc2626" : value < 0 ? "#16a34a" : "#94a3b8";
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-3 text-center">
      <div className="text-lg font-semibold" style={{ color }}>
        {value == null ? "n/a" : `${value > 0 ? "+" : ""}${value}${unit}`}
      </div>
      <div className="text-[10px] text-slate-500">{label}</div>
    </div>
  );
}

const RECOMMENDATION_LABEL: Record<ScenarioComparisonType["recommendation"], string> = {
  approve_for_field_review: "Approve for field review",
  reject: "Reject",
  needs_more_data: "Needs more data",
};

export function ScenarioComparison({ comparison }: { comparison: ScenarioComparisonType }) {
  const { overall_delta, recommendation } = comparison;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <DeltaCard label="Travel time change" value={overall_delta.average_travel_time_change_percent} />
        <DeltaCard label="Waiting time change" value={overall_delta.average_waiting_time_change_percent} />
        <DeltaCard label="Completed ratio change" value={overall_delta.completed_ratio_change_percent} />
        <DeltaCard label="Teleport delta" value={overall_delta.teleport_delta} unit="" />
      </div>
      <div className="rounded border border-slate-700 bg-slate-800/50 p-2 text-center text-sm font-semibold text-slate-100">
        Recommendation: {RECOMMENDATION_LABEL[recommendation]}
      </div>
    </div>
  );
}
