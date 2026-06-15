"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { register, login } from "@/lib/api";
import { Zap, ArrowRight, CheckCircle2 } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await register(email, password);
      await login(email, password);
      router.push("/");
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-noir-950">
      <div className="hidden w-1/2 flex-col justify-between bg-gradient-to-br from-noir-900 to-noir-950 p-12 lg:flex">
        <div className="flex items-center gap-2 text-noir-100">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-ls-400 to-ls-600 text-noir-950">
            <Zap size={18} strokeWidth={2.5} />
          </div>
          <span className="text-lg font-bold">LeadSignal</span>
        </div>
        <div className="space-y-6">
          <h2 className="text-3xl font-bold text-noir-100">Get the local edge.</h2>
          <ul className="space-y-4 text-noir-300">
            {[
              "Track hiring spikes, permits, and new businesses",
              "Map land-bank properties and parcel changes",
              "Receive daily email, Slack, and Discord digests",
              "Export leads to CSV or push to your CRM",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <CheckCircle2 size={18} className="text-ls-400" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="text-sm text-noir-500">© {new Date().getFullYear()} LeadSignal.</div>
      </div>

      <div className="flex w-full items-center justify-center p-6 lg:w-1/2">
        <div className="w-full max-w-md space-y-6 rounded-2xl border border-noir-800 bg-noir-900/50 p-8 shadow-glow">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-noir-100">Create your account</h1>
            <p className="mt-2 text-sm text-noir-400">Start turning public data into private deals.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm Password</Label>
              <Input id="confirm" type="password" placeholder="••••••••" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </div>
            {error && <div className="rounded-md bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating account..." : "Create account"} <ArrowRight size={16} className="ml-2" />
            </Button>
          </form>

          <p className="text-center text-sm text-noir-400">
            Already have an account?{" "}
            <Link href="/auth/login" className="font-medium text-ls-400 hover:text-ls-300">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
