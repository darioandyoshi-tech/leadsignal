"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { formatDistanceToNow } from "date-fns";
import { Signal } from "@/components/SignalTable";
import { TYPE_META } from "@/components/page-meta";

interface LiveTickerProps {
  signals: Signal[];
  maxItems?: number;
}

export function LiveTicker({ signals, maxItems = 6 }: LiveTickerProps) {
  const [visible, setVisible] = useState(signals.slice(0, maxItems));

  useEffect(() => {
    setVisible(signals.slice(0, maxItems));
  }, [signals, maxItems]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
        </span>
        <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Live feed</span>
      </div>
      <AnimatePresence mode="popLayout">
        {visible.map((s) => {
          const meta = TYPE_META[s.signal_type];
          const Icon = meta?.icon;
          return (
            <motion.div
              key={s.id}
              layout
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.35 }}
              className="flex items-center gap-3 rounded-lg border border-noir-700/50 bg-noir-900/40 p-3 backdrop-blur-sm"
            >
              {Icon && <Icon size={16} className={`text-${meta?.accent}-400 shrink-0`} />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-noir-200">{s.headline}</p>
                <p className="text-xs text-noir-500">{meta?.label || s.signal_type} · {s.location_name || "Omaha, NE"}</p>
              </div>
              <span className="shrink-0 text-xs tabular-nums text-noir-500">
                {formatDistanceToNow(new Date(s.detected_at), { addSuffix: true })}
              </span>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
