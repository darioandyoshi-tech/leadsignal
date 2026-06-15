"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Map as MapIcon,
  Bell,
  CreditCard,
  LogOut,
  Menu,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import React from "react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/map", label: "Map", icon: MapIcon },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/billing", label: "Billing", icon: CreditCard },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = React.useState<{ email?: string; tier?: string } | null>(null);
  const [mobileOpen, setMobileOpen] = React.useState(false);

  React.useEffect(() => {
    try {
      const raw = localStorage.getItem("token");
      if (!raw) return;
      const payload = JSON.parse(atob(raw.split(".")[1]));
      setUser({ email: payload.sub || "User", tier: payload.tier || "Free" });
    } catch {
      setUser(null);
    }
  }, []);

  function logout() {
    localStorage.removeItem("token");
    router.push("/auth/login");
  }

  return (
    <div className="flex min-h-screen bg-noir-950 text-noir-100">
      <aside className="hidden lg:flex w-64 flex-col border-r border-noir-800 bg-noir-900/50">
        <div className="flex h-16 items-center gap-2 px-6 border-b border-noir-800">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-ls-400 to-ls-600 text-noir-950">
            <Zap size={18} strokeWidth={2.5} />
          </div>
          <span className="text-lg font-bold tracking-tight">LeadSignal</span>
        </div>
        <nav className="flex-1 space-y-1 p-4">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "bg-noir-800 text-ls-300" : "text-noir-400 hover:bg-noir-800/50 hover:text-noir-200"
                )}
              >
                <Icon size={18} /> {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-noir-800 p-4">
          <div className="mb-3 text-sm">
            <div className="font-medium text-noir-100">{user?.email || "Guest"}</div>
            <div className="text-xs text-noir-500 capitalize">{user?.tier || "Free tier"}</div>
          </div>
          <Button variant="outline" className="w-full justify-start gap-2 border-noir-700 text-noir-300 hover:bg-noir-800" onClick={logout}>
            <LogOut size={16} /> Sign out
          </Button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-noir-800 bg-noir-900/50 px-4 lg:px-8">
          <div className="flex items-center gap-3 lg:hidden">
            <button className="rounded-md p-2 text-noir-400 hover:bg-noir-800" onClick={() => setMobileOpen(true)}>
              <Menu size={20} />
            </button>
            <span className="font-bold">LeadSignal</span>
          </div>
          <div className="hidden lg:block text-sm text-noir-400">Omaha, Nebraska · Local market intelligence</div>
          <div className="flex items-center gap-3">
            {user?.tier && (
              <span className="rounded-full border border-ls-500/30 bg-ls-500/10 px-3 py-1 text-xs font-medium text-ls-300">{user.tier}</span>
            )}
            <Button size="sm" className="hidden sm:flex" asChild>
              <Link href="/billing">Upgrade</Link>
            </Button>
          </div>
        </header>

        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-noir-950/80" onClick={() => setMobileOpen(false)} />
            <div className="absolute left-0 top-0 h-full w-64 bg-noir-900 p-4 border-r border-noir-800">
              <div className="mb-4 flex items-center justify-between">
                <span className="font-bold">LeadSignal</span>
                <button onClick={() => setMobileOpen(false)} className="text-noir-400"><X size={20} /></button>
              </div>
              <nav className="space-y-1">
                {NAV.map((item) => {
                  const active = pathname === item.href || pathname.startsWith(item.href + "/");
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={cn("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium", active ? "bg-noir-800 text-ls-300" : "text-noir-400")}
                    >
                      <Icon size={18} /> {item.label}
                    </Link>
                  );
                })}
              </nav>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-auto p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
