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

// Leaflet's default double-click-to-zoom fires two `click` events at the
// same point before the zoom happens, which this component would otherwise
// read as "corner 1, then corner 2" -- producing a zero-area bbox that the
// backend correctly rejects (min_lon/min_lat must be less than max/max),
// but with no indication to the user *why* their two clicks did nothing.
// Disabling doubleClickZoom (below, on MapContainer) prevents the zoom
// half of that; this distance guard is a second line of defense for two
// genuine single-clicks landing close enough together to still be
// unusable as a pilot-scale bbox.
const MIN_CORNER_SEPARATION_DEG = 0.0005; // ~50m at this latitude

export function BboxPicker({ centerLat, centerLon, zoom = 14, onBboxChange }: BboxPickerProps) {
  const [corner1, setCorner1] = useState<[number, number] | null>(null);
  const [corner2, setCorner2] = useState<[number, number] | null>(null);
  const [tooClose, setTooClose] = useState(false);

  function handleClick(lat: number, lon: number) {
    if (!corner1 || corner2) {
      // Nothing picked yet, or a full rectangle already exists -- start over.
      setCorner1([lat, lon]);
      setCorner2(null);
      setTooClose(false);
      onBboxChange(null);
      return;
    }
    if (
      Math.abs(lat - corner1[0]) < MIN_CORNER_SEPARATION_DEG &&
      Math.abs(lon - corner1[1]) < MIN_CORNER_SEPARATION_DEG
    ) {
      // Same spot as corner 1 (double-click, or two clicks too close
      // together to be a usable bbox) -- ignore it and keep waiting for a
      // genuinely different second corner instead of emitting a
      // zero/near-zero-area box.
      setTooClose(true);
      return;
    }
    setTooClose(false);
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
    <div className="relative h-full w-full">
      <MapContainer
        center={[centerLat, centerLon]}
        zoom={zoom}
        className="h-full w-full"
        scrollWheelZoom
        doubleClickZoom={false}
      >
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
      {tooClose && (
        <div className="pointer-events-none absolute bottom-2 left-2 z-[1000] rounded bg-red-950/90 px-2 py-1 text-[11px] text-red-200">
          That's too close to your first corner -- click a point further away for the opposite corner.
        </div>
      )}
    </div>
  );
}
