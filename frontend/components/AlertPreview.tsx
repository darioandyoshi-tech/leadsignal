"use client";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { format } from "date-fns";
import { Mail, Slack, MessageSquare, Webhook, FileSpreadsheet } from "lucide-react";
import React from "react";
import type { Signal } from "./SignalTable";

interface AlertPreviewProps {
  signals: Signal[];
  typeLabels: Record<string, string>;
}

const CHANNELS = [
  { key: "email", label: "Email digest", icon: Mail, default: true },
  { key: "slack", label: "Slack", icon: Slack },
  { key: "discord", label: "Discord", icon: MessageSquare },
  { key: "webhook", label: "Webhook", icon: Webhook },
  { key: "csv", label: "CSV export", icon: FileSpreadsheet },
];

function mockDigest(signals: Signal[], typeLabels: Record<string, string>) {
  const total = signals.length;
  const byType: Record<string, number> = {};
  for (const s of signals) byType[s.signal_type] = (byType[s.signal_type] || 0) + 1;
  const top = signals.slice(0, 5);
  let body = `LeadSignal Daily Digest — ${format(new Date(), "MMMM d, yyyy")}\n\n`;
  body += `${total} new signals detected in Omaha.\n\n`;
  body += `Breakdown:\n`;
  for (const [type, count] of Object.entries(byType)) body += `• ${typeLabels[type] || type}: ${count}\n`;
  body += `\nTop opportunities:\n`;
  for (const s of top) {
    body += `• [${typeLabels[s.signal_type] || s.signal_type}] ${s.headline}\n`;
    if (s.summary) body += `  ${s.summary.slice(0, 100).replace(/\n/g, " ")}...\n`;
  }
  return body;
}

export function AlertPreview({ signals, typeLabels }: AlertPreviewProps) {
  const [enabled, setEnabled] = React.useState<Record<string, boolean>>({
    email: true, slack: false, discord: false, webhook: false, csv: false,
  });
  const [preview, setPreview] = React.useState(mockDigest(signals, typeLabels));

  React.useEffect(() => {
    setPreview(mockDigest(signals, typeLabels));
  }, [signals, typeLabels]);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4 rounded-xl border border-noir-700 bg-noir-900/50 p-5">
        <h3 className="text-lg font-semibold text-noir-100">Alert channels</h3>
        <div className="space-y-3">
          {CHANNELS.map((ch) => {
            const Icon = ch.icon;
            return (
              <label key={ch.key} className="flex items-center justify-between rounded-lg border border-noir-800 bg-noir-900 p-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-md bg-noir-800 p-2 text-noir-300"><Icon size={18} /></div>
                  <div>
                    <div className="font-medium text-noir-200">{ch.label}</div>
                    <div className="text-xs text-noir-500">{ch.key === "email" ? "Sent daily at 7:00 AM" : "Configure in settings"}</div>
                  </div>
                </div>
                <Switch checked={enabled[ch.key]} onChange={(e: any) => setEnabled({ ...enabled, [ch.key]: e.target.checked })} />
              </label>
            );
          })}
        </div>
        <Button className="w-full">Save alert preferences</Button>
      </div>

      <div className="space-y-4 rounded-xl border border-noir-700 bg-noir-900/50 p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-noir-100">Preview</h3>
          <Badge variant="outline">Daily digest</Badge>
        </div>
        <Textarea value={preview} readOnly rows={16} className="font-mono text-xs leading-relaxed" />
        <Button variant="outline" className="w-full border-noir-700 text-noir-300 hover:bg-noir-800">Send test digest</Button>
      </div>
    </div>
  );
}
