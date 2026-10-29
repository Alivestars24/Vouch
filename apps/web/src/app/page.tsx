import type { Metadata } from "next";

import { WorkspaceHome } from "@/components/workspace-home";

export const metadata: Metadata = {
  title: "Workspace",
};

export default function HomePage() {
  return <WorkspaceHome />;
}
