"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { getTopOpportunities } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, AlertTriangle, Star, MapPin, Clock, Activity } from "lucide-react";

interface Opportunity {
  signal_id: string;
  symbol_or_company: string;
  signal_type: string;
  headline: string;
  score: number;
  rank: number;
  passed_dimensions: string[];
  failed_dimensions: string[];
  dimension_scores: Record<string, number>;
  metadata: {
    lat?: number;
    lng?: number;
    hours_ago?: number;
    velocity?: number;
    nearby_signals?: number;
    company_signal_count?: number;
  };
}

export function TopOpportunities({ limit = 8 }: { limit?: number }) {
  const [results, setResults] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await getTopOpportunities({ limit });
      setResults(data.results || []);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Failed to load opportunities");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [limit]);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: limit }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
        {error}
      </div>
    );
  }

  if (!results.length) {
    return (
      <div className="rounded-lg border border-dashed border-noir-700 p-4 text-center text-sm text-noir-400">
        No scored opportunities yet. Add more signals or tune criteria.
      </div>
    );
  }

  const accentForScore = (score: number) => {
    if (score >= 0.75) return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    if (score >= 0.55) return "bg-amber-500/20 text-amber-300 border-amber-500/30";
    return "bg-rose-500/20 text-rose-300 border-rose-500/30";
  };

  return (
    <div className="space-y-3">
      {results.map((opp, idx) => (
        <motion.div
          key={opp.signal_id}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: idx * 0.06 }}
          className="group relative rounded-xl border border-noir-700/50 bg-noir-900/40 p-4 backdrop-blur-sm transition-colors hover:bg-noir-900/70"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center gap-2 text-xs text-noir-400">
                <Badge variant="outline" className="capitalize">{opp.signal_type.replace(/_/g, " ")}</Badge>
                <span className="truncate">{opp.symbol_or_company}</span>
              </div>
              <h4 className="truncate text-sm font-medium text-noir-100">{opp.headline}</h4>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-noir-500">
                <span className="flex items-center gap-1">
                  <Clock size={12} /> {Math.round(opp.metadata.hours_ago || 0)}h ago
                </span>
                <span className="flex items-center gap-1">
                  <Activity size={12} /> velocity {opp.metadata.velocity}
                </span>
                {typeof opp.metadata.nearby_signals === "number" && opp.metadata.nearby_signals > 0 && (
                  <span className="flex items-center gap-1">
                    <MapPin size={12} /> {opp.metadata.nearby_signals} nearby
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <Badge className={`${accentForScore(opp.score)} border`}>
                <TrendingUp size={12} className="mr-1" />
                {Math.round(opp.score * 100)}
              </Badge>
              <span className="text-[10px] text-noir-500">#{opp.rank}</span>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-1">
            {opp.passed_dimensions.slice(0, 4).map((dim) => (
              <span
                key={dim}
                className="rounded-full bg-noir-800 px-2 py-0.5 text-[10px] capitalize text-noir-300"
              >
                {dim.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </motion.div>
      ))}
    </div>
  );
}
