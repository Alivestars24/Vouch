"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { IdentityProvider } from "@/components/identity-context";

export function ApplicationBoundary({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/creator" || pathname.startsWith("/creator/")) {
    return children;
  }

  return (
    <IdentityProvider>
      <AppShell>{children}</AppShell>
    </IdentityProvider>
  );
}
