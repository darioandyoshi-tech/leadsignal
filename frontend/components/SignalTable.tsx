"use client";

import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { format } from "date-fns";
import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import React from "react";

export interface Signal {
  id: string;
  company_id?: string;
  signal_type: string;
  severity: number;
  headline: string;
  summary?: string;
  source_url?: string;
  source_api?: string;
  location_name?: string;
  detected_at: string;
  published_at?: string;
  metadata?: Record<string, any>;
}

interface SignalTableProps {
  signals: Signal[];
  typeLabels: Record<string, string>;
}

const severityClass: Record<number, string> = {
  5: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  4: "bg-orange-500/15 text-orange-300 border-orange-500/30",
  3: "bg-ls-500/15 text-ls-300 border-ls-500/30",
  2: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  1: "bg-noir-700/50 text-noir-300 border-noir-600",
};

function SignalRow({ signal, typeLabels }: { signal: Signal; typeLabels: Record<string, string> }) {
  const [expanded, setExpanded] = React.useState(false);
  const typeLabel = typeLabels[signal.signal_type] || signal.signal_type;
  const severityStyle = severityClass[signal.severity] || severityClass[1];

  return (
    <React.Fragment>
      <TableRow className="cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <TableCell>
          <Badge variant="ghost" className={cn("border", severityStyle)}>{signal.severity}/5</Badge>
        </TableCell>
        <TableCell>
          <div className="font-medium text-noir-100">{signal.headline}</div>
          <div className="text-xs text-noir-500 mt-0.5">{typeLabel}</div>
        </TableCell>
        <TableCell className="hidden md:table-cell text-noir-400">{signal.location_name || "—"}</TableCell>
        <TableCell className="hidden sm:table-cell text-noir-400">
          {signal.detected_at ? format(new Date(signal.detected_at), "MMM d, h:mm a") : "—"}
        </TableCell>
        <TableCell className="text-right">
          <Button variant="ghost" size="sm" className="text-noir-400 hover:text-ls-300" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-noir-900/50">
          <TableCell colSpan={5} className="p-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold text-noir-200 mb-1">Summary</h4>
                <p className="text-sm text-noir-400 whitespace-pre-wrap">{signal.summary || "No summary provided."}</p>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-noir-500">Source API</span><span className="text-noir-300">{signal.source_api || "—"}</span></div>
                <div className="flex justify-between"><span className="text-noir-500">Detected</span><span className="text-noir-300">{signal.detected_at ? format(new Date(signal.detected_at), "PPpp") : "—"}</span></div>
                {signal.source_url && (
                  <div className="pt-2">
                    <a href={signal.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ls-400 hover:text-ls-300">View source <ExternalLink size={14} /></a>
                  </div>
                )}
              </div>
            </div>
          </TableCell>
        </TableRow>
      )}
    </React.Fragment>
  );
}

export function SignalTable({ signals, typeLabels }: SignalTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-24">Severity</TableHead>
          <TableHead>Signal</TableHead>
          <TableHead className="hidden md:table-cell">Location</TableHead>
          <TableHead className="hidden sm:table-cell">Detected</TableHead>
          <TableHead className="w-16"></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {signals.map((signal) => (
          <SignalRow key={signal.id} signal={signal} typeLabels={typeLabels} />
        ))}
      </TableBody>
    </Table>
  );
}
