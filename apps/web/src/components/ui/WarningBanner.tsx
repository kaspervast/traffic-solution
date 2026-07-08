export function WarningBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="border border-amber-700/50 bg-amber-950/40 px-4 py-2 text-xs text-amber-200">
      {children}
    </div>
  );
}

export function SumoEstimateWarning() {
  return (
    <WarningBanner>
      SUMO simulation is a planning estimate. It depends on OSM network quality and
      synthetic/calibrated demand. Field validation is required before operational changes.
    </WarningBanner>
  );
}

export function PilotScopeWarning() {
  return (
    <WarningBanner>
      This dashboard covers a 1 km-radius pilot zone in Rajkot only. Do not interpret any figure
      here as city-wide coverage.
    </WarningBanner>
  );
}

export function NetworkBuilderWarning() {
  return (
    <WarningBanner>
      Only the seeded Rajkot pilot network has TomTom-edge grounding out of the box. Networks
      built here need their own TomTom-edge mapping run (match-tomtom-segments) before AI
      scenario drafts for them will have live TomTom grounding -- until then, drafts will note
      grounding is unavailable rather than invent numbers. Keep new areas small (pilot-scale, not
      city-wide) -- this tool is not meant for large extracts.
    </WarningBanner>
  );
}
