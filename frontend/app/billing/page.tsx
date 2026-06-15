"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { createCheckout, getSubscription } from "@/lib/api";
import { Check, Zap, Building2, Rocket } from "lucide-react";

const TIERS = [
  {
    key: "starter",
    name: "Starter",
    price: "$49",
    period: "/mo",
    icon: Zap,
    description: "Perfect for a single sales rep who wants a daily pulse on local opportunities.",
    features: ["Email digest", "Dashboard access", "10 signals/day", "CSV export"],
    cta: "Start Starter",
    highlight: false,
  },
  {
    key: "pro",
    name: "Pro",
    price: "$149",
    period: "/mo",
    icon: Building2,
    description: "For small teams that need fast alerts across multiple channels.",
    features: ["Everything in Starter", "Slack + Discord alerts", "50 signals/day", "Webhook delivery", "Map view"],
    cta: "Start Pro",
    highlight: true,
  },
  {
    key: "growth",
    name: "Growth",
    price: "$399",
    period: "/mo",
    icon: Rocket,
    description: "Scale your local sales motion with full API access and unlimited signals.",
    features: ["Everything in Pro", "API access", "Unlimited signals", "Priority support", "Custom alert rules"],
    cta: "Start Growth",
    highlight: false,
  },
];

export default function BillingPage() {
  const [sub, setSub] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSubscription()
      .then(setSub)
      .catch(() => setSub(null))
      .finally(() => setLoading(false));
  }, []);

  async function subscribe(tier: string) {
    setCheckoutLoading(tier);
    setError("");
    try {
      const successUrl = `${window.location.origin}/billing?success=true`;
      const cancelUrl = `${window.location.origin}/billing?canceled=true`;
      const { url } = await createCheckout(tier, successUrl, cancelUrl);
      if (url) window.location.href = url;
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Could not start checkout");
    } finally {
      setCheckoutLoading(null);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-10">
        <div className="text-center">
          <Badge variant="outline" className="mb-3">Simple, transparent pricing</Badge>
          <h1 className="text-3xl font-bold text-noir-100">Get the local edge</h1>
          <p className="mt-2 text-noir-400">Turn public data into private deals. Cancel anytime.</p>
        </div>

        {sub?.status === "active" && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-center text-emerald-200">
            You are subscribed to the <strong>{sub.tier}</strong> plan.
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</div>
        )}

        <div className="grid gap-6 md:grid-cols-3">
          {TIERS.map((tier) => {
            const Icon = tier.icon;
            const current = sub?.tier === tier.key;
            return (
              <Card
                key={tier.key}
                className={`relative flex flex-col border p-6 ${
                  tier.highlight
                    ? "border-ls-500/50 bg-gradient-to-b from-ls-500/10 to-noir-900 shadow-glow"
                    : "border-noir-700 bg-noir-900/50"
                }`}
              >
                {tier.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-ls-500 px-3 py-1 text-xs font-semibold text-noir-950">
                    Most popular
                  </div>
                )}
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-noir-800 text-ls-300">
                  <Icon size={24} />
                </div>
                <h3 className="text-xl font-bold text-noir-100">{tier.name}</h3>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-noir-100">{tier.price}</span>
                  <span className="text-noir-500">{tier.period}</span>
                </div>
                <p className="mt-3 text-sm text-noir-400">{tier.description}</p>
                <ul className="mt-6 flex-1 space-y-3">
                  {tier.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-noir-300">
                      <Check size={16} className="mt-0.5 shrink-0 text-ls-400" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  className="mt-6 w-full"
                  variant={tier.highlight ? "default" : "outline"}
                  disabled={checkoutLoading === tier.key || current || loading}
                  onClick={() => subscribe(tier.key)}
                >
                  {current ? "Current Plan" : checkoutLoading === tier.key ? "Redirecting..." : tier.cta}
                </Button>
              </Card>
            );
          })}
        </div>

        <div className="rounded-xl border border-noir-700 bg-noir-900/50 p-6">
          <div className="flex flex-col items-start gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-noir-100">Enterprise?</h3>
              <p className="text-sm text-noir-400">Custom data sources, dedicated support, and SLA-backed delivery.</p>
            </div>
            <Button variant="outline" className="border-noir-700 text-noir-300 hover:bg-noir-800">Contact sales</Button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
