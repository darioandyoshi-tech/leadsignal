"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { SignalMap } from "@/components/SignalMap";
import { SignalFilters, Filters } from "@/components/SignalFilters";
import { Signal } from "@/components/SignalTable";
import { Skeleton } from "@/components/ui/skeleton";
import { getSignals } from "@/lib/api";

const TYPE_META: Record<string, { label: string }> = {
  hiring_spike: { label: "Hiring Spikes" },
  negative_review_cluster: { label: "Review Clusters" },
  permit_filing: { label: "Permit Filings" },
  parcel_change: { label: "Parcel Changes" },
  tax_delinquency: { label: "Tax Delinquency" },
  gov_contract_award: { label: "Gov Contracts" },
  business_license: { label: "Business Licenses" },
  ucc_filing: { label: "UCC Filings" },
  new_business_registration: { label: "New Businesses" },
  land_bank_property: { label: "Land Bank Properties" },
};

const DEFAULT_FILTERS: Filters = {
  search: "",
  signal_type: "land_bank_property",
  severity: "",
  source: "",
  date_from: "",
  date_to: "",
  sort: "detected_at_desc",
};

function filterSignals(signals: Signal[], filters: Filters) {
  const term = filters.search.toLowerCase();
  const severity = filters.severity ? parseInt(filters.severity, 10) : null;
  const from = filters.date_from ? new Date(filters.date_from) : null;

  return signals.filter((s) => {
    if (filters.signal_type && s.signal_type !== filters.signal_type) return false;
    if (severity !== null && s.severity !== severity) return false;
    if (filters.source && s.source_api !== filters.source) return false;
    if (from && new Date(s.detected_at) < from) return false;
    if (term) {
      const hay = [s.headline, s.summary, s.location_name, s.source_api, TYPE_META[s.signal_type]?.label]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!hay.includes(term)) return false;
    }
    return true;
  });
}

export default function MapPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  useEffect(() => {
    setLoading(true);
    getSignals({ signal_type: filters.signal_type || "land_bank_property", limit: 100 })
      .then((data) => setSignals(data || []))
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, [filters.signal_type]);

  const filtered = useMemo(() => filterSignals(signals, filters), [signals, filters]);

  const sources = useMemo(
    () => Array.from(new Set(signals.map((s) => s.source_api).filter((s): s is string => !!s))).sort(),
    [signals]
  );
  const types = useMemo(
    () => Object.entries(TYPE_META).map(([value, m]) => ({ value, label: m.label })),
    []
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-noir-100">Signal Map</h1>
          <p className="text-sm text-noir-400">Geocoded opportunities around Omaha. Land bank properties are shown by default.</p>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</div>
        )}

        <SignalFilters
          filters={filters}
          onChange={setFilters}
          sources={sources}
          types={types}
        />

        {loading ? (
          <Skeleton className="h-[500px] w-full" />
        ) : (
          <SignalMap
            signals={filtered}
            typeLabels={Object.fromEntries(Object.entries(TYPE_META).map(([k, m]) => [k, m.label]))}
          />
        )}

        <div className="rounded-lg border border-noir-800 bg-noir-900/50 p-4 text-sm text-noir-400">
          Showing {filtered.length.toLocaleString()} signals on the map. Addresses are geocoded on-demand via OpenStreetMap and cached in your browser.
        </div>
      </div>
    </AppShell>
  );
}
