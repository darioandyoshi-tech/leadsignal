"use client";

import { useEffect, useMemo, useState } from "react";
import type { Signal } from "./SignalTable";

const pinSvg = `data:image/svg+xml;base64,${btoa(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" stroke="#451a03" stroke-width="1.5"><path d="M12 21s-6.5-6.5-6.5-11A6.5 6.5 0 0 1 12 3.5a6.5 6.5 0 0 1 6.5 6.5c0 4.5-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.5" fill="#451a03"/></svg>`
)}`;

interface SignalMapProps {
  signals: Signal[];
  typeLabels: Record<string, string>;
  center?: [number, number];
  zoom?: number;
}

async function geocodeAddress(address: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`,
      { headers: { Accept: "application/json" } }
    );
    const data = await res.json();
    if (data && data[0]) {
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    }
  } catch {}
  return null;
}

export function SignalMap({ signals, typeLabels, center = [41.252, -95.998], zoom = 12 }: SignalMapProps) {
  const [mounted, setMounted] = useState(false);
  const [coords, setCoords] = useState<Record<string, { lat: number; lng: number }>>({});

  useEffect(() => {
    setMounted(true);
  }, []);

  const mappable = useMemo(() => {
    return signals.filter((s) => {
      const addr = s.location_name || s.metadata?.address || s.metadata?.property_address;
      return !!addr;
    });
  }, [signals]);

  useEffect(() => {
    if (!mounted) return;
    let cancelled = false;
    async function run() {
      const next: Record<string, { lat: number; lng: number }> = {};
      for (const s of mappable) {
        const addr = s.location_name || s.metadata?.address || s.metadata?.property_address;
        if (!addr) continue;
        const cached = localStorage.getItem(`geo:${addr}`);
        if (cached) {
          next[s.id] = JSON.parse(cached);
          continue;
        }
        const result = await geocodeAddress(`${addr}, Omaha, NE`);
        if (result) {
          localStorage.setItem(`geo:${addr}`, JSON.stringify(result));
          next[s.id] = result;
        }
        await new Promise((r) => setTimeout(r, 600));
      }
      if (!cancelled) setCoords(next);
    }
    run();
    return () => { cancelled = true; };
  }, [mappable, mounted]);

  const points = useMemo(() => {
    return mappable.filter((s) => coords[s.id]).map((s) => ({ ...s, ...coords[s.id] }));
  }, [mappable, coords]);

  const MapComponent = useMemo(
    () =>
      mounted
        ? import("react-leaflet").then((mod) => {
            const { MapContainer, TileLayer, Marker, Popup, useMap } = mod;
            const L = require("leaflet");
            require("leaflet/dist/leaflet.css");
            const markerIcon = new L.Icon({
              iconUrl: pinSvg,
              iconSize: [28, 36],
              iconAnchor: [14, 36],
              popupAnchor: [0, -32],
            });
            function BoundsSetter({ signals }: { signals: { lat: number; lng: number }[] }) {
              const map = useMap();
              useEffect(() => {
                if (signals.length === 0) return;
                if (signals.length === 1) {
                  map.setView([signals[0].lat, signals[0].lng], 15);
                  return;
                }
                const bounds = L.latLngBounds(signals.map((s) => [s.lat, s.lng]));
                map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
              }, [map, signals]);
              return null;
            }
            return function LoadedMap({ points, typeLabels }: any) {
              return (
                <MapContainer center={center} zoom={zoom} scrollWheelZoom={true} className="h-full w-full">
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  <BoundsSetter signals={points.map((p: any) => ({ lat: p.lat, lng: p.lng }))} />
                  {points.map((s: any) => (
                    <Marker key={s.id} position={[s.lat, s.lng]} icon={markerIcon}>
                      <Popup>
                        <div className="min-w-[200px]">
                          <div className="font-semibold text-noir-900">{s.headline}</div>
                          <div className="text-xs text-noir-600 mt-1">
                            {typeLabels[s.signal_type] || s.signal_type} · Severity {s.severity}
                          </div>
                          {s.source_url && (
                            <a href={s.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-blue-600 hover:underline">View source</a>
                          )}
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>
              );
            };
          })
        : null,
    [mounted]
  );

  const [LoadedMap, setLoadedMap] = useState<React.FC<any> | null>(null);

  useEffect(() => {
    if (MapComponent) {
      MapComponent.then((C) => setLoadedMap(() => C));
    }
  }, [MapComponent]);

  return (
    <div className="h-[500px] w-full overflow-hidden rounded-xl border border-noir-700">
      {LoadedMap ? <LoadedMap points={points} typeLabels={typeLabels} /> : <div className="h-full w-full bg-noir-900/50" />}
    </div>
  );
}
