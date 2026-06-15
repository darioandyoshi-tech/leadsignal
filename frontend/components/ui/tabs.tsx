"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const TabsContext = React.createContext<{
  value: string;
  onChange: (value: string) => void;
} | null>(null);

function useTabs() {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error("Tabs components must be used inside Tabs");
  return ctx;
}

function Tabs({ value, onValueChange, children, className }: { value: string; onValueChange: (v: string) => void; children: React.ReactNode; className?: string }) {
  return (
    <TabsContext.Provider value={{ value, onChange: onValueChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

function TabsList({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("inline-flex items-center gap-1 rounded-lg border border-noir-700 bg-noir-900/50 p-1", className)}>
      {children}
    </div>
  );
}

function TabsTrigger({ value, children, className }: { value: string; children: React.ReactNode; className?: string }) {
  const ctx = useTabs();
  const active = ctx.value === value;
  return (
    <button
      onClick={() => ctx.onChange(value)}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active ? "bg-noir-800 text-ls-300" : "text-noir-400 hover:bg-noir-800/50 hover:text-noir-200",
        className
      )}
    >
      {children}
    </button>
  );
}

function TabsContent({ value, children, className }: { value: string; children: React.ReactNode; className?: string }) {
  const ctx = useTabs();
  if (ctx.value !== value) return null;
  return <div className={cn("animate-in fade-in duration-200", className)}>{children}</div>;
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
