import type { ScenarioComparison } from "@/types";

const IMPACT_COLOR: Record<string, string> = {
  better: "#16a34a",
  worse: "#dc2626",
  unchanged: "#94a3b8",
};

export function EdgeImpactTable({ edgeImpacts }: { edgeImpacts: ScenarioComparison["edge_impacts"] }) {
  if (edgeImpacts.length === 0) {
    return <p className="text-xs text-slate-500">No per-edge impact data for this comparison.</p>;
  }
  return (
    <table className="w-full text-left text-xs">
      <thead className="uppercase text-slate-500">
        <tr>
          <th className="p-1">Edge</th>
          <th className="p-1">Road</th>
          <th className="p-1">Speed change</th>
          <th className="p-1">Waiting time change (s)</th>
          <th className="p-1">Impact</th>
        </tr>
      </thead>
      <tbody>
        {edgeImpacts.map((e) => (
          <tr key={e.sumo_edge_id} className="border-t border-slate-800">
            <td className="p-1">{e.sumo_edge_id}</td>
            <td className="p-1">{e.road_name ?? "unknown"}</td>
            <td className="p-1">{e.speed_change_percent == null ? "n/a" : `${e.speed_change_percent}%`}</td>
            <td className="p-1">{e.waiting_time_change_sec ?? "n/a"}</td>
            <td className="p-1 font-semibold" style={{ color: IMPACT_COLOR[e.impact] }}>
              {e.impact}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
