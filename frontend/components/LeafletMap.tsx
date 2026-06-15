"use client";

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";

interface Point {
  id: string;
  lat: number;
  lng: number;
  headline: string;
  signal_type: string;
  severity: number;
  source_url?: string;
}

interface LeafletMapProps {
  points: Point[];
  typeLabels: Record<string, string>;
  center?: [number, number];
  zoom?: number;
}

const pinSvg = `data:image/svg+xml;base64,${btoa(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" stroke="#451a03" stroke-width="1.5"><path d="M12 21s-6.5-6.5-6.5-11A6.5 6.5 0 0 1 12 3.5a6.5 6.5 0 0 1 6.5 6.5c0 4.5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.5" fill="#451a03"/></svg>`
)}`;

function BoundsSetter({ points }: { points: { lat: number; lng: number }[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView([points[0].lat, points[0].lng], 15);
      return;
    }
    const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
  }, [map, points]);
  return null;
}

export default function LeafletMap({
  points,
  typeLabels,
  center = [41.252, -95.998],
  zoom = 12,
}: LeafletMapProps) {
  const markerIcon = useMemo(
    () =>
      new L.Icon({
        iconUrl: pinSvg,
        iconSize: [28, 36],
        iconAnchor: [14, 36],
        popupAnchor: [0, -32],
      }),
    []
  );

  if (points.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-noir-900/50 text-sm text-noir-400">
        No mappable signals match the current filter.
      </div>
    );
  }

  return (
    <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} className="h-full w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <BoundsSetter points={points.map((p) => ({ lat: p.lat, lng: p.lng }))} />
      {points.map((s) => (
        <Marker key={s.id} position={[s.lat, s.lng]} icon={markerIcon}>
          <Popup>
            <div className="min-w-[200px]">
              <div className="font-semibold text-noir-900">{s.headline}</div>
              <div className="text-xs text-noir-600 mt-1">
                {typeLabels[s.signal_type] || s.signal_type} · Severity {s.severity}
              </div>
              {s.source_url && (
                <a
                  href={s.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-xs text-blue-600 hover:underline"
                >
                  View source
                </a>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
