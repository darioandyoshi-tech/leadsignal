'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getSignals, getSignalStats, sendDigest, getSubscription } from '@/lib/api';

export default function Dashboard() {
  const router = useRouter();
  const [signals, setSignals] = useState<any[]>([]);
  const [stats, setStats] = useState({ hiring_spike: 0, negative_review_cluster: 0, permit_filing: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [user, setUser] = useState<{ email?: string; tier?: string } | null>(null);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    if (!token) {
      router.push('/auth/login');
      return;
    }
    load();
  }, [router]);

  async function load() {
    try {
      setLoading(true);
      const [sigData, statData, subData] = await Promise.all([
        getSignals({ limit: 50 }),
        getSignalStats(),
        getSubscription().catch(() => null),
      ]);
      setSignals(sigData);
      setStats(statData);
      setUser(subData);
    } catch (e: any) {
      if (e.response?.status === 401) {
        localStorage.removeItem('token');
        router.push('/auth/login');
      } else {
        setError(e.response?.data?.detail || e.message);
      }
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem('token');
    router.push('/auth/login');
  }

  const typeLabels: Record<string, string> = {
    hiring_spike: '💼 Hiring Spike',
    negative_review_cluster: '⭐ Negative Reviews',
    permit_filing: '🏗️ Permit Filing',
  };

  return (
    <main className="max-w-5xl mx-auto p-6">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">LeadSignal</h1>
          <p className="text-slate-600">Local market opportunity scanner for Omaha, Nebraska</p>
        </div>
        <div className="flex items-center gap-3">
          {user?.tier && (
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
              {user.tier}
            </span>
          )}
          <Link href="/billing">
            <Button variant="outline">Pricing</Button>
          </Link>
          <Button variant="ghost" onClick={logout}>Sign out</Button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard title="Total Signals" value={stats.total} />
        <StatCard title="Hiring Spikes" value={stats.hiring_spike} />
        <StatCard title="Review Clusters" value={stats.negative_review_cluster} />
        <StatCard title="Permit Filings" value={stats.permit_filing} />
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Latest Signals</h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </Button>
          <Button onClick={sendDigest}>Send Digest</Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-md">{error}</div>
      )}

      <div className="space-y-4">
        {signals.map((s) => (
          <Card key={s.id}>
            <CardHeader>
              <CardTitle className="text-base">
                {typeLabels[s.signal_type] || s.signal_type} — {s.headline}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-slate-500 mb-2">
                Severity: {s.severity}/5 • Detected: {new Date(s.detected_at).toLocaleString()}
              </div>
              {s.summary && (
                <pre className="whitespace-pre-wrap text-sm text-slate-700 bg-slate-100 p-3 rounded">{s.summary}</pre>
              )}
              {s.source_url && (
                <a href={s.source_url} target="_blank" rel="noreferrer" className="text-blue-600 text-sm hover:underline">
                  View source →
                </a>
              )}
            </CardContent>
          </Card>
        ))}
        {signals.length === 0 && !loading && (
          <div className="text-slate-500">No signals yet. Run the scraper to populate data.</div>
        )}
      </div>
    </main>
  );
}

function StatCard({ title, value }: { title: string; value: number }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-slate-500">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}
