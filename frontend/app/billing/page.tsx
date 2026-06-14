'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { createCheckout, getSubscription } from '@/lib/api';

const TIERS = [
  { key: 'starter', name: 'Starter', price: '$49/mo', features: ['Email digest', 'Dashboard access', '10 signals/day'] },
  { key: 'pro', name: 'Pro', price: '$149/mo', features: ['Slack + Discord alerts', 'CSV export', '50 signals/day', 'Webhook delivery'] },
  { key: 'growth', name: 'Growth', price: '$399/mo', features: ['API access', 'Unlimited signals', 'Priority support', 'Custom alert rules'] },
];

export default function BillingPage() {
  const [sub, setSub] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getSubscription()
      .then(setSub)
      .catch(() => setSub(null))
      .finally(() => setLoading(false));
  }, []);

  async function subscribe(tier: string) {
    setCheckoutLoading(tier);
    setError('');
    try {
      const successUrl = `${window.location.origin}/billing?success=true`;
      const cancelUrl = `${window.location.origin}/billing?canceled=true`;
      const { url } = await createCheckout(tier, successUrl, cancelUrl);
      if (url) window.location.href = url;
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Could not start checkout');
    } finally {
      setCheckoutLoading(null);
    }
  }

  return (
    <main className="max-w-5xl mx-auto p-6">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight">Pricing</h1>
        <p className="text-slate-600">Unlock local market signals for Omaha, Nebraska</p>
      </header>

      {sub?.status === 'active' && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-md">
          You are subscribed to the <strong>{sub.tier}</strong> plan.
        </div>
      )}

      {error && <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {TIERS.map((tier) => (
          <Card key={tier.key} className={sub?.tier === tier.key ? 'ring-2 ring-blue-500' : ''}>
            <CardHeader>
              <CardTitle>{tier.name}</CardTitle>
              <CardDescription className="text-2xl font-bold text-slate-900">{tier.price}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ul className="space-y-2 text-sm text-slate-600">
                {tier.features.map((f, i) => (
                  <li key={i}>✓ {f}</li>
                ))}
              </ul>
              <Button
                className="w-full"
                disabled={checkoutLoading === tier.key || sub?.tier === tier.key}
                onClick={() => subscribe(tier.key)}
              >
                {checkoutLoading === tier.key ? 'Redirecting...' : sub?.tier === tier.key ? 'Current Plan' : 'Subscribe'}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
