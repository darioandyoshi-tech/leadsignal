"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

interface AnimatedStatCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  change?: number;
  accent?: "amber" | "emerald" | "rose" | "blue" | "slate";
  delay?: number;
}

const accentGradients: Record<string, string> = {
  amber: "from-amber-500/20 via-amber-500/5 to-transparent",
  emerald: "from-emerald-500/20 via-emerald-500/5 to-transparent",
  rose: "from-rose-500/20 via-rose-500/5 to-transparent",
  blue: "from-blue-500/20 via-blue-500/5 to-transparent",
  slate: "from-slate-500/20 via-slate-500/5 to-transparent",
};

const accentBorders: Record<string, string> = {
  amber: "border-amber-500/30",
  emerald: "border-emerald-500/30",
  rose: "border-rose-500/30",
  blue: "border-blue-500/30",
  slate: "border-slate-500/30",
};

export function AnimatedStatCard({
  title,
  value,
  icon,
  change,
  accent = "amber",
  delay = 0,
}: AnimatedStatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={`relative overflow-hidden rounded-xl border ${accentBorders[accent]} bg-noir-900/60 p-5 backdrop-blur-md`}
    >
      <div
        className={`absolute inset-0 bg-gradient-to-br ${accentGradients[accent]} opacity-60`}
      />
      <div className="relative z-10 flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-noir-400">{title}</p>
          <h3 className="mt-2 text-2xl font-bold tabular-nums text-noir-100">{value}</h3>
          {change !== undefined && (
            <p
              className={`mt-1 text-xs font-medium ${
                change >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {change >= 0 ? "↑" : "↓"} {Math.abs(change).toFixed(1)}%
            </p>
          )}
        </div>
        <div className="rounded-lg bg-noir-800/80 p-2 text-noir-200">{icon}</div>
      </div>
    </motion.div>
  );
}
