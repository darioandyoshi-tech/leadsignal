"use client";

import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { format } from "date-fns";

export interface TrendPoint {
  date: string;
  value: number;
}

export function TrendChart({ data, label = "Signals" }: { data: TrendPoint[]; label?: string }) {
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorSignal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <XAxis dataKey="date" tickFormatter={(d) => format(new Date(d), "MMM d")} stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
          <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px", color: "#f1f5f9" }}
            itemStyle={{ color: "#fbbf24" }}
            labelFormatter={(d) => format(new Date(d), "PPP")}
          />
          <Area type="monotone" dataKey="value" name={label} stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorSignal)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
