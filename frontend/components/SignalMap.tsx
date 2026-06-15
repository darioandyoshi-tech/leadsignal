"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import type { Signal } from "./SignalTable";

const LeafletMap = dynamic(() => import("@/components/LeafletMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-noir-900/50 text-sm text-noir-400">
      Loading map…
    </div>
  ),
});

interface SignalMapProps {
  signals: Signal[];
  typeLabels: Record<string, string>;
  center?: [number, number];
  zoom?: number;
}

async function geocodeAddress(address: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`,
      { headers: { Accept: "application/json" } }
    );
    if (!res.ok) return null;
    const data = await res.json();
    if (data && data[0]) {
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    }
  } catch {}
  return null;
}

export function SignalMap({ signals, typeLabels, center = [41.252, -95.998], zoom = 12 }: SignalMapProps) {
  const [coords, setCoords] = useState<Record<string, { lat: number; lng: number }>>({});

  const mappable = useMemo(() => {
    return signals.filter((s) => {
      return (s.lat != null && s.lng != null) || !!(s.location_name || s.metadata?.address || s.metadata?.property_address);
    });
  }, [signals]);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      const next: Record<string, { lat: number; lng: number }> = {};
      const needGeocode: { signal: Signal; addr: string }[] = [];
      for (const s of mappable) {
        if (s.lat != null && s.lng != null) {
          next[s.id] = { lat: s.lat, lng: s.lng };
          continue;
        }
        const addr = s.location_name || s.metadata?.address || s.metadata?.property_address;
        if (!addr) continue;
        const cached = localStorage.getItem(`geo:${addr}`);
        if (cached) {
          next[s.id] = JSON.parse(cached);
          continue;
        }
        needGeocode.push({ signal: s, addr });
      }

      // Geocode in serial with a small delay to respect Nominatim rate limits.
      for (const { signal, addr } of needGeocode) {
        const result = await geocodeAddress(`${addr}, Omaha, NE`);
        if (result) {
          localStorage.setItem(`geo:${addr}`, JSON.stringify(result));
          next[signal.id] = result;
        }
        await new Promise((r) => setTimeout(r, 650));
      }
      if (!cancelled) setCoords(next);
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [mappable]);

  const points = useMemo(() => {
    return mappable
      .filter((s) => coords[s.id])
      .map((s) => ({ ...s, ...coords[s.id] }));
  }, [mappable, coords]);

  return (
    <div className="h-[500px] w-full overflow-hidden rounded-xl border border-noir-700">
      <LeafletMap points={points} typeLabels={typeLabels} center={center} zoom={zoom} />
    </div>
  );
}
