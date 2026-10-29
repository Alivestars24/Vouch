import type { Metadata } from "next";

import { TrackWorkspace } from "@/components/track-workspace";

export const metadata: Metadata = {
  title: "Track campaign outcomes",
};

export default function TrackPage() {
  return <TrackWorkspace />;
}
