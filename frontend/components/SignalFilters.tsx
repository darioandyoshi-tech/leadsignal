"use client";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface Filters {
  search: string;
  signal_type: string;
  severity: string;
  source: string;
  date_from: string;
  date_to: string;
  sort: string;
}

interface SignalFiltersProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
  sources: string[];
  types: { value: string; label: string }[];
  className?: string;
}

const SEVERITIES = [
  { value: "", label: "Any severity" },
  { value: "5", label: "5 — Critical" },
  { value: "4", label: "4 — High" },
  { value: "3", label: "3 — Medium" },
  { value: "2", label: "2 — Low" },
  { value: "1", label: "1 — Info" },
];

const SORTS = [
  { value: "detected_at_desc", label: "Newest first" },
  { value: "detected_at_asc", label: "Oldest first" },
  { value: "severity_desc", label: "Severity high → low" },
  { value: "severity_asc", label: "Severity low → high" },
];

export function SignalFilters({ filters, onChange, sources, types, className }: SignalFiltersProps) {
  function update(key: keyof Filters, value: string) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <div className={cn("grid gap-3 rounded-xl border border-noir-700 bg-noir-900/50 p-4 md:grid-cols-2 lg:grid-cols-7", className)}>
      <Input
        placeholder="Search headline, summary, location..."
        value={filters.search}
        onChange={(e) => update("search", e.target.value)}
        className="lg:col-span-2"
      />
      <Select value={filters.signal_type} onChange={(e) => update("signal_type", e.target.value)}>
        <option value="">All signal types</option>
        {types.map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </Select>
      <Select value={filters.severity} onChange={(e) => update("severity", e.target.value)}>
        {SEVERITIES.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </Select>
      <Select value={filters.source} onChange={(e) => update("source", e.target.value)}>
        <option value="">All sources</option>
        {sources.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </Select>
      <Input type="date" value={filters.date_from} onChange={(e) => update("date_from", e.target.value)} />
      <Select value={filters.sort} onChange={(e) => update("sort", e.target.value)}>
        {SORTS.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </Select>
    </div>
  );
}
