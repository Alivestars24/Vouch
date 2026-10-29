import type { Metadata } from "next";

import { FindWorkspace } from "@/components/find/find-workspace";

export const metadata: Metadata = {
  title: "Find creators",
};

export default function FindPage() {
  return <FindWorkspace />;
}
