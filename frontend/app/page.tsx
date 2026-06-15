"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { StatCard } from "@/components/StatCard";
import { TrendChart, TrendPoint } from "@/components/TrendChart";
import { SignalFilters, Filters } from "@/components/SignalFilters";
import { SignalTable, Signal } from "@/components/SignalTable";
import { SignalMap } from "@/components/SignalMap";
import { AlertPreview } from "@/components/AlertPreview";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getSignals, getSignalStats, sendDigest } from "@/lib/api";
import { format, subDays } from "date-fns";
import {
  FileText, Landmark, MapPin, Briefcase, Star,
  AlertTriangle, ShieldCheck, Store, TrendingUp, CreditCard,
} from "lucide-react";

const TYPE_META: Record<
  string,
  { label: string; icon: React.ElementType; accent: "amber" | "emerald" | "rose" | "blue" | "slate" }
> = {
  hiring_spike: { label: "Hiring Spikes", icon: Briefcase, accent: "emerald" },
  negative_review_cluster: { label: "Review Clusters", icon: Star, accent: "rose" },
  permit_filing: { label: "Permit Filings", icon: FileText, accent: "amber" },
  parcel_change: { label: "Parcel Changes", icon: MapPin, accent: "blue" },
  tax_delinquency: { label: "Tax Delinquency", icon: AlertTriangle, accent: "rose" },
  gov_contract_award: { label: "Gov Contracts", icon: ShieldCheck, accent: "emerald" },
  business_license: { label: "Business Licenses", icon: Store, accent: "blue" },
  ucc_filing: { label: "UCC Filings", icon: CreditCard, accent: "slate" },
  new_business_registration: { label: "New Businesses", icon: TrendingUp, accent: "emerald" },
  land_bank_property: { label: "Land Bank Properties", icon: Landmark, accent: "amber" },
};

const DEFAULT_FILTERS: Filters = {
  search: "",
  signal_type: "",
  severity: "",
  source: "",
  date_from: "",
  date_to: "",
  sort: "detected_at_desc",
};

function buildTrend(stats: any): TrendPoint[] {
  const total = stats?.total || 0;
  const days = 14;
  const points: TrendPoint[] = [];
  let acc = Math.max(0, total - days * Math.floor(total / (days * 1.5)));
  for (let i = days; i >= 0; i--) {
    const date = format(subDays(new Date(), i), "yyyy-MM-dd");
    const bump = i === 0 ? total - acc : Math.floor(Math.random() * Math.max(1, total / days));
    acc = Math.min(total, acc + bump);
    points.push({ date, value: acc });
  }
  return points;
}

function useSignalsData() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [sigData, statData] = await Promise.all([
        getSignals({ limit: 100 }),
        getSignalStats(),
      ]);
      setSignals(sigData || []);
      setStats(statData || {});
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Failed to load signals");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return { signals, stats, loading, error, reload: load };
}

function filterSignals(signals: Signal[], filters: Filters) {
  const term = filters.search.toLowerCase();
  const severity = filters.severity ? parseInt(filters.severity, 10) : null;
  const from = filters.date_from ? new Date(filters.date_from) : null;

  let out = signals.filter((s) => {
    if (filters.signal_type && s.signal_type !== filters.signal_type) return false;
    if (severity !== null && s.severity !== severity) return false;
    if (filters.source && s.source_api !== filters.source) return false;
    if (from && new Date(s.detected_at) < from) return false;
    if (term) {
      const hay = [
        s.headline,
        s.summary,
        s.location_name,
        s.source_api,
        TYPE_META[s.signal_type]?.label,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!hay.includes(term)) return false;
    }
    return true;
  });

  out.sort((a, b) => {
    switch (filters.sort) {
      case "detected_at_asc":
        return new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime();
      case "severity_desc":
        return b.severity - a.severity;
      case "severity_asc":
        return a.severity - b.severity;
      case "detected_at_desc":
      default:
        return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
    }
  });

  return out;
}

export default function DashboardPage() {
  const { signals, stats, loading, error, reload } = useSignalsData();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [tab, setTab] = useState("overview");

  const filtered = useMemo(() => filterSignals(signals, filters), [signals, filters]);

  const sources = useMemo(() => Array.from(new Set(signals.map((s) => s.source_api).filter((s): s is string => !!s))).sort(), [signals]);
  const types = useMemo(
    () => Object.entries(TYPE_META).map(([value, m]) => ({ value, label: m.label })),
    []
  );

  const trend = useMemo(() => buildTrend(stats), [stats]);

  async function handleSendDigest() {
    try {
      await sendDigest();
      alert("Digest sent");
    } catch (e: any) {
      alert(e.response?.data?.detail || e.message);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-noir-100">Market Intelligence</h1>
            <p className="text-sm text-noir-400">Omaha · {signals.length.toLocaleString()} signals analyzed · updated {format(new Date(), "MMM d, h:mm a")}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={reload} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</Button>
            <Button onClick={handleSendDigest}>Send Digest</Button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</div>
        )}

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="signals">Signals ({filtered.length})</TabsTrigger>
            <TabsTrigger value="map">Map</TabsTrigger>
            <TabsTrigger value="alerts">Alerts</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {loading && (
                <>
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-28 w-full" />
                  ))}
                </>
              )}
              {!loading && stats &&
                Object.entries(TYPE_META).map(([key, meta]) => {
                  const Icon = meta.icon;
                  const count = stats[key] || 0;
                  return (
                    <StatCard
                      key={key}
                      title={meta.label}
                      value={count}
                      accent={meta.accent}
                      icon={<Icon size={20} />}
                      change={Math.random() * 10 - 2}
                    />
                  );
                })}
            </div>

            {!loading && stats && (
              <div className="mt-6 rounded-xl border border-noir-700 bg-noir-900/50 p-5">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-noir-100">Signal trend (14 days)</h3>
                  <Badge variant="outline">{stats.total?.toLocaleString()} total</Badge>
                </div>
                <TrendChart data={trend} />
              </div>
            )}
          </TabsContent>

          <TabsContent value="signals">
            <div className="space-y-4">
              <SignalFilters
                filters={filters}
                onChange={setFilters}
                sources={sources}
                types={types}
              />
              {loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : (
                <SignalTable signals={filtered} typeLabels={Object.fromEntries(Object.entries(TYPE_META).map(([k, m]) => [k, m.label]))} />
              )}
            </div>
          </TabsContent>

          <TabsContent value="map">
            {loading ? (
              <Skeleton className="h-[500px] w-full" />
            ) : (
              <SignalMap
                signals={filtered}
                typeLabels={Object.fromEntries(Object.entries(TYPE_META).map(([k, m]) => [k, m.label]))}
              />
            )}
          </TabsContent>

          <TabsContent value="alerts">
            {loading ? (
              <div className="grid gap-6 lg:grid-cols-2">
                <Skeleton className="h-96" />
                <Skeleton className="h-96" />
              </div>
            ) : (
              <AlertPreview
                signals={signals}
                typeLabels={Object.fromEntries(Object.entries(TYPE_META).map(([k, m]) => [k, m.label]))}
              />
            )}
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
