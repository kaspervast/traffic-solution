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
