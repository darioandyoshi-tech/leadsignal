"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

interface StatCardProps {
  title: string;
  value: number;
  change?: number;
  icon?: React.ReactNode;
  accent?: "amber" | "emerald" | "rose" | "blue" | "slate";
}

export function StatCard({ title, value, change, icon, accent = "slate" }: StatCardProps) {
  const accents = {
    amber: "from-ls-500/20 to-ls-600/5 border-ls-500/30 text-ls-300",
    emerald: "from-emerald-500/20 to-emerald-600/5 border-emerald-500/30 text-emerald-300",
    rose: "from-rose-500/20 to-rose-600/5 border-rose-500/30 text-rose-300",
    blue: "from-blue-500/20 to-blue-600/5 border-blue-500/30 text-blue-300",
    slate: "from-noir-700/50 to-noir-800/20 border-noir-700 text-noir-300",
  };

  return (
    <div className={cn("relative overflow-hidden rounded-xl border bg-gradient-to-br p-5", accents[accent])}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-medium text-noir-400">{title}</div>
          <div className="mt-2 text-3xl font-bold tracking-tight text-noir-100">{value.toLocaleString()}</div>
          {change !== undefined && (
            <div className={cn("mt-1 inline-flex items-center gap-1 text-xs font-medium", change >= 0 ? "text-emerald-400" : "text-rose-400")}>
              {change >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {Math.abs(change).toFixed(1)}%
            </div>
          )}
        </div>
        {icon && <div className="text-noir-500">{icon}</div>}
      </div>
    </div>
  );
}
