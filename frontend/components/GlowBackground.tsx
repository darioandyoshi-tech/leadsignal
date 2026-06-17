"use client";

import { ReactNode } from "react";

export function GlowBackground({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-noir-950">
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -left-1/4 -top-1/4 h-[60vw] w-[60vw] rounded-full bg-ls-500/10 blur-[120px]" />
        <div className="absolute -right-1/4 bottom-0 h-[50vw] w-[50vw] rounded-full bg-blue-500/10 blur-[120px]" />
        <div className="absolute left-1/3 top-1/2 h-[30vw] w-[30vw] -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-500/5 blur-[100px]" />
      </div>
      <div className="relative z-10">{children}</div>
    </div>
  );
}
