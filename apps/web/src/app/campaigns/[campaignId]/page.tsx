import type { Metadata } from "next";

import { CampaignWorkspace } from "@/components/campaign-workspace";

export const metadata: Metadata = { title: "Campaign review" };

export default async function CampaignPage({
  params,
}: {
  params: Promise<{ campaignId: string }>;
}) {
  const { campaignId } = await params;
  return <CampaignWorkspace campaignId={campaignId} />;
}
