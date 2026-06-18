"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown, Minus, Target, Shield, Clock } from "lucide-react";

interface StockPick {
  id: string;
  symbol: string;
  score: number;
  action: "buy" | "hold" | "avoid";
  confidence: number;
  forecast_return_4d: number | null;
  predicted_close_4d: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  max_hold_days: number;
  reasoning: string;
  run_date: string;
}

export function StockPicks({ limit = 15 }: { limit?: number }) {
  const [picks, setPicks] = useState<StockPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/market/picks", { params: { active_only: true, limit } });
      setPicks(data.picks || []);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || "Failed to load picks");
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
          <Skeleton key={i} className="h-24 w-full" />
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

  if (!picks.length) {
    return (
      <div className="rounded-lg border border-dashed border-noir-700 p-4 text-center text-sm text-noir-400">
        No active stock picks. Run the daily market scan first.
      </div>
    );
  }

  const badgeForAction = (action: string) => {
    const base = "capitalize border";
    if (action === "buy") return `${base} bg-emerald-500/20 text-emerald-300 border-emerald-500/30`;
    if (action === "hold") return `${base} bg-amber-500/20 text-amber-300 border-amber-500/30`;
    return `${base} bg-rose-500/20 text-rose-300 border-rose-500/30`;
  };

  const Icon = (action: string) => {
    if (action === "buy") return <TrendingUp size={14} />;
    if (action === "avoid") return <TrendingDown size={14} />;
    return <Minus size={14} />;
  };

  return (
    <div className="space-y-3">
      {picks.map((pick, idx) => (
        <motion.div
          key={pick.id}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: idx * 0.05 }}
          className="group rounded-xl border border-noir-700/50 bg-noir-900/40 p-4 backdrop-blur-sm transition-colors hover:bg-noir-900/70"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center gap-2">
                <Badge className={badgeForAction(pick.action)}>
                  {Icon(pick.action)}
                  <span className="ml-1">{pick.action}</span>
                </Badge>
                <span className="text-lg font-bold text-noir-100">{pick.symbol}</span>
                <span className="text-xs text-noir-500">Score {Math.round(pick.score * 100)}</span>
              </div>
              <p className="text-sm text-noir-300">{pick.reasoning}</p>

              <div className="mt-3 flex flex-wrap gap-4 text-xs text-noir-400">
                {pick.forecast_return_4d !== null && (
                  <span className="flex items-center gap-1">
                    <Target size={12} /> 4d forecast {(pick.forecast_return_4d * 100).toFixed(1)}%
                  </span>
                )}
                {pick.take_profit !== null && (
                  <span className="flex items-center gap-1 text-emerald-300">
                    <TrendingUp size={12} /> Target ${pick.take_profit.toFixed(2)}
                  </span>
                )}
                {pick.stop_loss !== null && (
                  <span className="flex items-center gap-1 text-rose-300">
                    <Shield size={12} /> Stop ${pick.stop_loss.toFixed(2)}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Clock size={12} /> Max hold {pick.max_hold_days}d
                </span>
              </div>
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
