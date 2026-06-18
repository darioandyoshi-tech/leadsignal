"use client";

import { motion } from "framer-motion";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { format, addDays, parseISO } from "date-fns";

export interface ForecastPoint {
  date: string;
  value: number;
  isForecast?: boolean;
  lower10?: number;
  upper90?: number;
}

interface ForecastChartProps {
  data: ForecastPoint[];
  title?: string;
  color?: string;
  forecastStartIndex?: number;
}

export function ForecastChart({
  data,
  title,
  color = "#f59e0b",
  forecastStartIndex,
}: ForecastChartProps) {
  if (!data.length) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-noir-700 text-sm text-noir-400">
        No forecast data
      </div>
    );
  }

  const startIndex = forecastStartIndex ?? data.findIndex((d) => d.isForecast) ?? data.length;
  const forecastDate = startIndex >= 0 && startIndex < data.length ? data[startIndex].date : null;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="w-full"
    >
      {title && <h4 className="mb-2 text-sm font-medium text-noir-200">{title}</h4>}
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`fc-${color}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d) => format(parseISO(d), "MMM d")}
              stroke="#64748b"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: "8px",
                color: "#f1f5f9",
              }}
              itemStyle={{ color }}
              labelFormatter={(d) => format(parseISO(d as string), "PPP")}
            />
            {forecastDate && (
              <ReferenceLine
                x={forecastDate}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={{ value: "Forecast", position: "top", fill: "#94a3b8", fontSize: 12 }}
              />
            )}
            <Area
              type="monotone"
              dataKey="upper90"
              stroke="transparent"
              fill={`url(#fc-${color})`}
              fillOpacity={1}
            />
            <Area
              type="monotone"
              dataKey="lower10"
              stroke="transparent"
              fill="#0f172a"
              fillOpacity={1}
              baseLine={0}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              name="Forecast"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
