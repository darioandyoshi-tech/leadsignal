"use client";

import { useEffect, useState, useMemo } from "react";
import { AppShell } from "@/components/AppShell";
import { AlertPreview } from "@/components/AlertPreview";
import { Signal } from "@/components/SignalTable";
import { Skeleton } from "@/components/ui/skeleton";
import { getSignals } from "@/lib/api";

const TYPE_META: Record<string, { label: string }> = {
  hiring_spike: { label: "Hiring Spikes" },
  negative_review_cluster: { label: "Review Clusters" },
  permit_filing: { label: "Permit Filings" },
  parcel_change: { label: "Parcel Changes" },
  tax_delinquency: { label: "Tax Delinquency" },
  gov_contract_award: { label: "Gov Contracts" },
  business_license: { label: "Business Licenses" },
  ucc_filing: { label: "UCC Filings" },
  new_business_registration: { label: "New Businesses" },
  land_bank_property: { label: "Land Bank Properties" },
};

export default function AlertsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getSignals({ limit: 500 })
      .then((data) => setSignals(data || []))
      .catch((e) => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  }, []);

  const typeLabels = useMemo(
    () => Object.fromEntries(Object.entries(TYPE_META).map(([k, m]) => [k, m.label])),
    []
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-noir-100">Alerts</h1>
          <p className="text-sm text-noir-400">Choose where you want your signals delivered and preview the daily digest.</p>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</div>
        )}

        {loading ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Skeleton className="h-96" />
            <Skeleton className="h-96" />
          </div>
        ) : (
          <AlertPreview signals={signals} typeLabels={typeLabels} />
        )}
      </div>
    </AppShell>
  );
}
