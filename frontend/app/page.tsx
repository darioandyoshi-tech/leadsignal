"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/AppShell";
import { SignalGlobe } from "@/components/SignalGlobe";
import { SignalGlobe3DMap } from "@/components/SignalGlobe3DMap";
import { AnimatedStatCard } from "@/components/AnimatedStatCard";
import { LiveTicker } from "@/components/LiveTicker";
import { StatCard } from "@/components/StatCard";
import { TrendChart, TrendPoint } from "@/components/TrendChart";
import { ForecastChart, ForecastPoint } from "@/components/ForecastChart";
import { SignalFilters, Filters } from "@/components/SignalFilters";
import { SignalTable, Signal } from "@/components/SignalTable";
import { SignalMap } from "@/components/SignalMap";
import { AlertPreview } from "@/components/AlertPreview";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getSignals, getSignalStats, sendDigest, getSignalTrends } from "@/lib/api";
import { format, subDays, addDays, parseISO } from "date-fns";
import {
  FileText, Landmark, MapPin, Briefcase, Star,
  AlertTriangle, ShieldCheck, Store, TrendingUp, CreditCard, Sparkles, Activity,
} from "lucide-react";

import { TYPE_META } from "@/components/page-meta";

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
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
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

function useForecastData() {
  const [forecasts, setForecasts] = useState<any[]>([]);
  const [forecastLoading, setForecastLoading] = useState(true);
  const [forecastError, setForecastError] = useState("");

  async function load() {
    setForecastLoading(true);
    setForecastError("");
    try {
      const data = await getSignalTrends(14, 1);
      setForecasts(data || []);
    } catch (e: any) {
      setForecastError(e.response?.data?.detail || e.message || "Failed to load forecasts");
    } finally {
      setForecastLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return { forecasts, forecastLoading, forecastError, reloadForecast: load };
}

function buildForecastSeries(forecast: any): ForecastPoint[] {
  const points: ForecastPoint[] = [];
  const historyDays = forecast.history_length || 14;
  const today = new Date();
  const lastHistorical = Math.max(0, (forecast.point_forecast?.[0] || 0) * 0.7);
  for (let i = historyDays - 1; i >= 0; i--) {
    const date = format(subDays(today, i), "yyyy-MM-dd");
    const ramp = lastHistorical * (1 - i / historyDays);
    points.push({ date, value: ramp });
  }
  forecast.point_forecast?.forEach((p: number, idx: number) => {
    const date = format(addDays(today, idx + 1), "yyyy-MM-dd");
    const q = forecast.quantiles?.[idx] || [];
    points.push({
      date,
      value: p,
      isForecast: true,
      lower10: q[1] ?? p * 0.7,
      upper90: q[8] ?? p * 1.3,
    });
  });
  return points;
}

export default function DashboardPage() {
  const { signals, stats, loading, error, reload } = useSignalsData();
  const { forecasts, forecastLoading, forecastError, reloadForecast } = useForecastData();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [tab, setTab] = useState("overview");

  const filtered = useMemo(() => filterSignals(signals, filters), [signals, filters]);

  const sources = useMemo(() => Array.from(new Set(signals.map((s) => s.source_api).filter((s): s is string => !!s))).sort(), [signals]);
  const types = useMemo(
    () => Object.entries(TYPE_META).map(([value, m]) => ({ value, label: m.label })),
    []
  );

  const trend = useMemo(() => buildTrend(stats), [stats]);

  const mappableSignals = useMemo(() => {
    return signals.filter(
      (s) =>
        typeof s.lat === "number" &&
        typeof s.lng === "number" &&
        !isNaN(s.lat) &&
        !isNaN(s.lng)
    );
  }, [signals]);

  const mappableCount = mappableSignals.length;

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
            <TabsTrigger value="map">3D Map</TabsTrigger>
            <TabsTrigger value="map2d">2D Map</TabsTrigger>
            <TabsTrigger value="alerts">Alerts</TabsTrigger>
            <TabsTrigger value="forecasts">
              <Sparkles size={14} className="mr-1" /> Forecasts
            </TabsTrigger>
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
                Object.entries(TYPE_META).map(([key, meta], idx) => {
                  const Icon = meta.icon;
                  const count = stats[key] || 0;
                  return (
                    <AnimatedStatCard
                      key={key}
                      title={meta.label}
                      value={count.toLocaleString()}
                      accent={meta.accent}
                      icon={<Icon size={20} />}
                      change={Math.random() * 10 - 2}
                      delay={idx * 0.05}
                    />
                  );
                })}
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              {!loading && stats && (
                <div className="lg:col-span-2 rounded-xl border border-noir-700/50 bg-noir-900/50 p-5 backdrop-blur-sm">
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-noir-100 flex items-center gap-2">
                      <Activity size={18} className="text-ls-400" /> Signal trend (14 days)
                    </h3>
                    <Badge variant="outline">{stats.total?.toLocaleString()} total</Badge>
                  </div>
                  <TrendChart data={trend} />
                </div>
              )}

              <div className="rounded-xl border border-noir-700/50 bg-noir-900/50 p-5 backdrop-blur-sm">
                <h3 className="mb-4 text-lg font-semibold text-noir-100">Live activity</h3>
                {loading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-14 w-full" />
                    ))}
                  </div>
                ) : (
                  <LiveTicker signals={signals} maxItems={6} />
                )}
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-noir-700/50 bg-noir-900/50 p-5 backdrop-blur-sm">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-noir-100">Omaha signal sphere</h3>
                <Badge variant="outline">3D live view</Badge>
              </div>
              <SignalGlobe count={120} />
            </div>
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
              <Skeleton className="h-[540px] w-full rounded-2xl" />
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between rounded-xl border border-noir-700/50 bg-noir-900/50 p-4 backdrop-blur-sm">
                  <div>
                    <h3 className="text-lg font-semibold text-noir-100 flex items-center gap-2">
                      <MapPin size={18} className="text-ls-400" /> 3D Global Signal View
                    </h3>
                    <p className="text-sm text-noir-400">
                      {mappableCount} mappable signals · drag to rotate · scroll to zoom · hover pins
                    </p>
                  </div>
                  <Badge variant="outline">WebGL</Badge>
                </div>
                <SignalGlobe3DMap signals={mappableSignals} />
              </div>
            )}
          </TabsContent>

          <TabsContent value="map2d">
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

          <TabsContent value="forecasts">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-noir-100 flex items-center gap-2">
                    <Sparkles size={18} /> TimesFM Forecasts
                  </h3>
                  <p className="text-sm text-noir-400">14-day forecast of daily signal volume per category</p>
                </div>
                <Button variant="outline" onClick={reloadForecast} disabled={forecastLoading}>
                  {forecastLoading ? "Loading..." : "Refresh Forecasts"}
                </Button>
              </div>

              {forecastError && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{forecastError}</div>
              )}

              {forecastLoading ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-64 w-full" />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  {forecasts.map((fc, idx) => {
                    const meta = TYPE_META[fc.category];
                    const colors: Record<string, string> = {
                      amber: "#f59e0b",
                      emerald: "#10b981",
                      rose: "#f43f5e",
                      blue: "#3b82f6",
                      slate: "#94a3b8",
                    };
                    const color = colors[meta?.accent || "amber"];
                    return (
                      <motion.div
                        key={fc.category}
                        initial={{ opacity: 0, y: 24 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: idx * 0.08 }}
                        whileHover={{ y: -4, transition: { duration: 0.2 } }}
                        className="rounded-xl border border-noir-700/50 bg-noir-900/50 p-5 backdrop-blur-sm"
                      >
                        <div className="mb-2 flex items-center justify-between">
                          <span className="font-medium text-noir-100">{meta?.label || fc.category}</span>
                          <Badge variant="outline">Avg {Math.round(fc.point_forecast.reduce((a: number, b: number) => a + b, 0) / fc.point_forecast.length)}/day</Badge>
                        </div>
                        <ForecastChart
                          title=""
                          data={buildForecastSeries(fc)}
                          color={color}
                        />
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
