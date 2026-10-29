import type { Metadata } from "next";

import { OAuthCallback } from "@/components/oauth-callback";

export const metadata: Metadata = { title: "Complete sign-in", referrer: "no-referrer" };

export default function AuthCallbackPage() {
  return <OAuthCallback />;
}
