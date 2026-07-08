"use client";

import "leaflet/dist/leaflet.css";
import { useState } from "react";
import { CircleMarker, MapContainer, Rectangle, TileLayer, useMapEvents } from "react-leaflet";

/** [minLon, minLat, maxLon, maxLat] -- matches the bbox string format used
 * throughout the backend (Overpass "map" export, TomTom incidentDetails). */
export type Bbox = [number, number, number, number];

interface BboxPickerProps {
  centerLat: number;
  centerLon: number;
  zoom?: number;
  onBboxChange: (bbox: Bbox | null) => void;
}

/** No plain-Leaflet-draw dependency -- click once for one corner, click
 * again for the opposite corner, click a third time to start over. Must be
 * rendered inside <MapContainer> since useMapEvents relies on the Leaflet
 * map context. */
function ClickCapture({ onClick }: { onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export function BboxPicker({ centerLat, centerLon, zoom = 14, onBboxChange }: BboxPickerProps) {
  const [corner1, setCorner1] = useState<[number, number] | null>(null);
  const [corner2, setCorner2] = useState<[number, number] | null>(null);

  function handleClick(lat: number, lon: number) {
    if (!corner1 || corner2) {
      // Nothing picked yet, or a full rectangle already exists -- start over.
      setCorner1([lat, lon]);
      setCorner2(null);
      onBboxChange(null);
      return;
    }
    setCorner2([lat, lon]);
    const minLat = Math.min(corner1[0], lat);
    const maxLat = Math.max(corner1[0], lat);
    const minLon = Math.min(corner1[1], lon);
    const maxLon = Math.max(corner1[1], lon);
    onBboxChange([minLon, minLat, maxLon, maxLat]);
  }

  const bounds: [[number, number], [number, number]] | null =
    corner1 && corner2
      ? [
          [Math.min(corner1[0], corner2[0]), Math.min(corner1[1], corner2[1])],
          [Math.max(corner1[0], corner2[0]), Math.max(corner1[1], corner2[1])],
        ]
      : null;

  return (
    <MapContainer center={[centerLat, centerLon]} zoom={zoom} className="h-full w-full" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickCapture onClick={handleClick} />
      {corner1 && !corner2 && (
        <CircleMarker
          center={corner1}
          radius={6}
          pathOptions={{ color: "#f97316", fillColor: "#f97316", fillOpacity: 0.9 }}
        />
      )}
      {bounds && <Rectangle bounds={bounds} pathOptions={{ color: "#f97316", weight: 2, fillOpacity: 0.1 }} />}
    </MapContainer>
  );
}
