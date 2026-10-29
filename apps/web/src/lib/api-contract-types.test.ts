import { expectTypeOf, it } from "vitest";

import type { components, paths } from "@/lib/generated/api";

type Schemas = components["schemas"];

it("generates required separate affirmative notice authorization from the backend", () => {
  type Upload = Schemas["UploadIntentCreate"];
  expectTypeOf<Upload["notice_acknowledged"]>().toEqualTypeOf<true>();
  expectTypeOf<Upload["purpose"]>().toEqualTypeOf<"campaign_check">();
  expectTypeOf<Upload["notice_version"]>().toEqualTypeOf<string>();
  expectTypeOf<Upload["rights_attested"]>().toEqualTypeOf<boolean>();
  expectTypeOf<Omit<Upload, "notice_acknowledged">>().not.toExtend<Upload>();
  expectTypeOf<Omit<Upload, "purpose">>().not.toExtend<Upload>();
  expectTypeOf<Omit<Upload, "notice_version">>().not.toExtend<Upload>();
});

it("schemas public notices and scoped receipts without treating generic responses as trusted DTOs", () => {
  type NoticeResponse = paths["/api/v1/notices/campaign-check"]["get"]["responses"][200]["content"]["application/json"];
  type ReceiptResponse = paths["/api/v1/consent-receipts/{receipt_id}"]["get"]["responses"][200]["content"]["application/json"];
  expectTypeOf<NoticeResponse>().toEqualTypeOf<Schemas["ProcessingNotice"]>();
  expectTypeOf<NoticeResponse["status"]>().toEqualTypeOf<"draft_local_only">();
  expectTypeOf<ReceiptResponse>().toEqualTypeOf<Schemas["ConsentReceiptRead"]>();
  expectTypeOf<ReceiptResponse["revocation_actor_kind"]>().toEqualTypeOf<"member" | "retention" | null>();
  expectTypeOf<ReceiptResponse["revoked_at"]>().toEqualTypeOf<string | null>();
});
