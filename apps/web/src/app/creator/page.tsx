import type { Metadata } from "next";

import { CreatorPortal } from "@/components/creator-portal";

export const metadata: Metadata = {
  title: "Creator campaign",
  description: "Private creator campaign submission and feedback view.",
  referrer: "no-referrer",
  robots: {
    index: false,
    follow: false,
    noarchive: true,
    nocache: true,
  },
};

export default function CreatorPage() {
  return <CreatorPortal />;
}
