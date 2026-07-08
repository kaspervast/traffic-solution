"use client";

import "leaflet/dist/leaflet.css";
import { Circle, MapContainer, Polyline, TileLayer, Tooltip } from "react-leaflet";
import type { SumoEdgeOut } from "@/types";

interface SumoMapLayerProps {
  centerLat: number;
  centerLon: number;
  radiusM: number;
  edges: SumoEdgeOut[];
  selectedEdgeId: string | null;
  onSelectEdge: (sumoEdgeId: string) => void;
}

export function SumoMapLayer({ centerLat, centerLon, radiusM, edges, selectedEdgeId, onSelectEdge }: SumoMapLayerProps) {
  return (
    <MapContainer center={[centerLat, centerLon]} zoom={15} className="h-full w-full" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle
        center={[centerLat, centerLon]}
        radius={radiusM}
        pathOptions={{ color: "#38bdf8", fillOpacity: 0.02, weight: 1, dashArray: "4 4" }}
      />
      {edges.map((edge) => {
        const positions = edge.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]);
        const isSelected = edge.sumo_edge_id === selectedEdgeId;
        return (
          <Polyline
            key={edge.id}
            positions={positions}
            pathOptions={{
              color: isSelected ? "#f97316" : "#64748b",
              weight: isSelected ? 5 : 2,
              opacity: isSelected ? 1 : 0.6,
            }}
            eventHandlers={{ click: () => onSelectEdge(edge.sumo_edge_id) }}
          >
            <Tooltip sticky>
              {edge.road_name ?? "Unnamed edge"} ({edge.sumo_edge_id}) · {edge.num_lanes ?? "?"} lane(s)
            </Tooltip>
          </Polyline>
        );
      })}
    </MapContainer>
  );
}
