import type { Metadata } from "next";

import { TryReadiness } from "@/components/try-readiness";

export const metadata: Metadata = { title: "Try readiness" };

export default function TryPage() {
  return <TryReadiness />;
}
