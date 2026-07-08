"use client";

import "leaflet/dist/leaflet.css";
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import type { AOI, Anomaly, FlowObservation, Incident, ProbePoint } from "@/types";
import { SEVERITY_COLORS } from "@/types";

interface LiveMapProps {
  aoi?: AOI;
  probePoints: ProbePoint[];
  observationsByProbe: Record<string, FlowObservation>;
  incidents: Incident[];
  anomaliesByProbe: Record<string, Anomaly>;
}

const DEFAULT_CENTER: [number, number] = [22.329077, 70.769564];

function probeColor(probeId: string, anomaliesByProbe: Record<string, Anomaly>): string {
  const anomaly = anomaliesByProbe[probeId];
  if (anomaly) return SEVERITY_COLORS[anomaly.severity];
  return "#38bdf8"; // no active anomaly -> neutral blue
}

export function LiveMap({ aoi, probePoints, observationsByProbe, incidents, anomaliesByProbe }: LiveMapProps) {
  const center: [number, number] = aoi ? [aoi.center_lat, aoi.center_lon] : DEFAULT_CENTER;
  const radius = aoi?.radius_m ?? 1000;

  return (
    <MapContainer center={center} zoom={15} className="h-full w-full" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle
        center={center}
        radius={radius}
        pathOptions={{ color: "#38bdf8", fillOpacity: 0.03, weight: 1, dashArray: "4 4" }}
      />
      {probePoints.map((p) => {
        const obs = observationsByProbe[p.id];
        const color = probeColor(p.id, anomaliesByProbe);
        return (
          <CircleMarker
            key={p.id}
            center={[p.lat, p.lon]}
            radius={7}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 2 }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-semibold">{p.name}</div>
                <div className="text-xs text-slate-500">priority: {p.priority}</div>
                {obs ? (
                  <div className="mt-1">
                    <div>Speed: {obs.current_speed_kmph ?? "n/a"} km/h (free-flow {obs.free_flow_speed_kmph ?? "n/a"})</div>
                    <div>Delay: {obs.delay_sec ?? "n/a"} s</div>
                    <div className="text-[10px] text-slate-400">observed {new Date(obs.observed_at).toLocaleTimeString()}</div>
                  </div>
                ) : (
                  <div className="mt-1 text-xs text-slate-400">No observation yet.</div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
      {incidents
        .filter((inc) => inc.lat != null && inc.lon != null)
        .map((inc) => (
          <CircleMarker
            key={inc.id}
            center={[inc.lat as number, inc.lon as number]}
            radius={6}
            pathOptions={{ color: "#f97316", fillColor: "#f97316", fillOpacity: 0.9 }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-semibold">{inc.description ?? "Incident (no description from TomTom)"}</div>
                <div>{inc.from_text ?? "unknown"} → {inc.to_text ?? "unknown"}</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
