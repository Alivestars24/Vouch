import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ApplicationBoundary } from "@/components/application-boundary";

import "@fontsource-variable/space-grotesk/wght.css";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./globals.css";
import "./tokens.css";
import "./product-design.css";

export const metadata: Metadata = {
  title: {
    default: "Vouch · Creator campaign workspace",
    template: "%s · Vouch",
  },
  description: "Build creator campaigns, inspect evidence and record exact-version decisions.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ApplicationBoundary>{children}</ApplicationBoundary>
      </body>
    </html>
  );
}
