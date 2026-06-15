"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/lib/api";
import { Zap, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
      router.push("/");
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Login failed");
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
        <div className="space-y-4">
          <blockquote className="text-2xl font-semibold leading-snug text-noir-100">
            "The best local sales reps know what is happening before the competition does. LeadSignal makes that automatic."
          </blockquote>
          <p className="text-noir-400">— Built for Omaha, built for hustlers.</p>
        </div>
        <div className="text-sm text-noir-500">© {new Date().getFullYear()} LeadSignal.</div>
      </div>

      <div className="flex w-full items-center justify-center p-6 lg:w-1/2">
        <div className="w-full max-w-md space-y-6 rounded-2xl border border-noir-800 bg-noir-900/50 p-8 shadow-glow">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-noir-100">Welcome back</h1>
            <p className="mt-2 text-sm text-noir-400">Sign in to your LeadSignal account.</p>
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
            {error && <div className="rounded-md bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign In"} <ArrowRight size={16} className="ml-2" />
            </Button>
          </form>

          <p className="text-center text-sm text-noir-400">
            Don&apos;t have an account?{" "}
            <Link href="/auth/register" className="font-medium text-ls-400 hover:text-ls-300">Sign up</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
