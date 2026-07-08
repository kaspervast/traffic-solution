"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAOI } from "@/lib/hooks";
import { NetworkBuilderWarning } from "@/components/ui/WarningBanner";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import type { BboxSummary, ImportOsmResult } from "@/types";
import type { Bbox } from "@/components/map/BboxPicker";

const BboxPicker = dynamic(() => import("@/components/map/BboxPicker").then((m) => m.BboxPicker), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-slate-500">Loading map…</div>,
});

function formatBbox(bbox: Bbox): string {
  return bbox.map((v) => v.toFixed(6)).join(",");
}

export default function NetworkBuilderPage() {
  const aoiQuery = useAOI();
  const [bbox, setBbox] = useState<Bbox | null>(null);
  const [name, setName] = useState("New pilot scenario");
  const [durationSeconds, setDurationSeconds] = useState(3600);
  const [demandPeriod, setDemandPeriod] = useState(3.0);
  const [fringeFactor, setFringeFactor] = useState(5.0);
  const [seed, setSeed] = useState(42);
  const [result, setResult] = useState<ImportOsmResult | null>(null);

  const bboxSummaryQuery = useQuery({
    queryKey: ["bbox-summary", bbox],
    queryFn: () =>
      api.get<BboxSummary>(
        `/api/traffic/bbox-summary?min_lon=${bbox![0]}&min_lat=${bbox![1]}&max_lon=${bbox![2]}&max_lat=${bbox![3]}`,
      ),
    enabled: !!bbox,
    retry: false,
  });

  const buildMutation = useMutation({
    mutationFn: async () => {
      if (!bbox) throw new Error("Pick a bbox on the map first");
      if (!aoiQuery.data?.id) throw new Error("AOI not loaded yet");
      setResult(null);
      return api.post<ImportOsmResult>("/api/sumo/networks/import-osm", {
        name,
        bbox: formatBbox(bbox),
        aoi_id: aoiQuery.data.id,
        duration_seconds: durationSeconds,
        demand_period: demandPeriod,
        fringe_factor: fringeFactor,
        seed,
      });
    },
    onSuccess: (data) => setResult(data),
  });

  const center = aoiQuery.data
    ? { lat: aoiQuery.data.center_lat, lon: aoiQuery.data.center_lon }
    : { lat: 22.329077, lon: 70.769564 };

  return (
    <div className="flex h-[calc(100vh-49px)] flex-col">
      <NetworkBuilderWarning />
      <div className="grid flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[1.3fr_1fr]">
        <div className="relative h-[45vh] lg:h-auto">
          <BboxPicker centerLat={center.lat} centerLon={center.lon} onBboxChange={setBbox} />
          <div className="pointer-events-none absolute left-2 top-2 z-[1000] rounded bg-slate-950/80 px-2 py-1 text-[11px] text-slate-300">
            Click once for one corner, click again for the opposite corner. Click a third time to redo.
          </div>
        </div>

        <div className="flex flex-col gap-3 overflow-y-auto border-l border-slate-800 p-4">
          <div className="rounded border border-slate-800 bg-slate-900 p-3">
            <h3 className="mb-2 text-sm font-semibold text-slate-200">Selected area</h3>
            {bbox ? (
              <div className="text-xs text-slate-300">
                <div className="font-mono">{formatBbox(bbox)}</div>
                <div className="mt-1 text-[10px] text-slate-500">minLon,minLat,maxLon,maxLat</div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No area selected yet -- click twice on the map.</p>
            )}

            {bbox && bboxSummaryQuery.isLoading && (
              <p className="mt-2 text-xs text-slate-500">Checking live TomTom incidents in this area…</p>
            )}
            {bbox && bboxSummaryQuery.isError && (
              <div className="mt-2">
                <ErrorNotice
                  message={
                    bboxSummaryQuery.error instanceof ApiError
                      ? bboxSummaryQuery.error.message
                      : "Could not fetch TomTom incident summary for this area."
                  }
                />
              </div>
            )}
            {bboxSummaryQuery.data && (
              <div className="mt-2 rounded border border-slate-700 bg-slate-800/50 p-2 text-xs text-slate-200">
                <div>{bboxSummaryQuery.data.incident_count} active TomTom incident(s) in this area right now.</div>
                {Object.keys(bboxSummaryQuery.data.by_magnitude_of_delay).length > 0 && (
                  <ul className="mt-1 text-[11px] text-slate-400">
                    {Object.entries(bboxSummaryQuery.data.by_magnitude_of_delay).map(([label, count]) => (
                      <li key={label}>
                        {label}: {count}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="rounded border border-slate-800 bg-slate-900 p-3">
            <h3 className="mb-2 text-sm font-semibold text-slate-200">Scenario settings</h3>
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
                Duration (s)
                <input
                  type="number"
                  min={60}
                  value={durationSeconds}
                  onChange={(e) => setDurationSeconds(Number(e.target.value))}
                  className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
                />
              </label>
              <label>
                Demand period (s/veh)
                <input
                  type="number"
                  step={0.1}
                  min={0.1}
                  value={demandPeriod}
                  onChange={(e) => setDemandPeriod(Number(e.target.value))}
                  className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
                />
              </label>
              <label>
                Fringe factor
                <input
                  type="number"
                  step={0.5}
                  min={0.1}
                  value={fringeFactor}
                  onChange={(e) => setFringeFactor(Number(e.target.value))}
                  className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
                />
              </label>
              <label>
                Random seed
                <input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                  className="mt-0.5 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1"
                />
              </label>
            </div>

            <button
              onClick={() => buildMutation.mutate()}
              disabled={!bbox || buildMutation.isPending}
              className="mt-3 w-full rounded bg-orange-700 px-3 py-1.5 text-xs text-white hover:bg-orange-600 disabled:opacity-50"
            >
              {buildMutation.isPending ? "Generating network…" : "Generate network"}
            </button>
            {buildMutation.isPending && (
              <p className="mt-1 text-[10px] text-slate-500">
                This can take 30s-2min depending on area size (OSM download + netconvert + demand
                generation). Please wait -- do not resubmit.
              </p>
            )}
          </div>

          {buildMutation.isError && (
            <ErrorNotice
              message={
                buildMutation.error instanceof ApiError ? buildMutation.error.message : "Network build failed."
              }
            />
          )}

          {result && (
            <div className="rounded border border-emerald-800 bg-emerald-950/30 p-3 text-xs text-emerald-100">
              <div className="mb-1 font-semibold uppercase text-emerald-300">Network created</div>
              <ul className="space-y-0.5">
                <li>Network: {result.network_name}</li>
                <li>Edges imported: {result.edges_created}</li>
                {result.edges_skipped_no_shape > 0 && <li>Edges skipped (no shape): {result.edges_skipped_no_shape}</li>}
                <li>Junctions: {result.junction_count ?? "n/a"}</li>
                <li>Vehicles (baseline demand): {result.vehicle_count ?? "n/a"}</li>
                <li>Network validated: {result.validated ? "yes" : "no"}</li>
              </ul>
              <Link
                href={`/sumo-lab?network=${result.network_id}`}
                className="mt-2 inline-block rounded bg-emerald-700 px-3 py-1.5 text-xs text-white hover:bg-emerald-600"
              >
                Open in SUMO What-If Lab
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
