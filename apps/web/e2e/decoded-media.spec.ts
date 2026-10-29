import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test("decoded private upload rejects corrupt media and keeps Check evidence synthetic", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const credentials = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../.local/credentials.json"), "utf8"));
  const fixture = resolve(import.meta.dirname, "../../../.local/fixtures/decoded-blue-2s.mp4");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("marketer@vouch.test");
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review pipeline" })).toBeVisible();
  await expect(page.locator(".campaign-table, .state-panel.empty").first()).toBeVisible();
  const drawer = page.locator("details.create-drawer");
  if ((await drawer.getAttribute("open")) === null) await drawer.locator("summary").click();
  const name = `Decoded browser ${Date.now()}`;
  await page.getByRole("textbox", { name: "Campaign name" }).fill(name);
  await page.getByRole("button", { name: "Create campaign", exact: true }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText("Decoded media processing", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Use synthetic MP4" })).toHaveCount(0);

  const input = page.getByLabel("MP4 or WebM video", { exact: true });
  await input.setInputFiles({
    name: "header-only.mp4", mimeType: "video/mp4",
    buffer: Buffer.from("AAAAGGZ0eXBpc29tAAACAGlzb21pc28y", "base64"),
  });
  const caption = page.getByRole("textbox", { name: "Caption snapshot" });
  await caption.fill("Authorized synthetic blue video, not a model observation.");
  const rights = page.getByRole("checkbox", { name: /authorized to upload/ });
  await rights.check();
  const acknowledgment = page.getByRole("checkbox", { name: /I acknowledge the processing notice/ });
  await acknowledgment.check();
  await page.locator(".upload-panel").screenshot({ path: testInfo.outputPath("processing-notice-intake.png") });
  await page.getByRole("button", { name: "Create submission", exact: true }).click();
  await expect(page.locator(".upload-panel").getByRole("alert")).toContainText("Media could not be safely decoded");
  await expect(caption).toHaveValue("Authorized synthetic blue video, not a model observation.");
  await expect(rights).toBeChecked();
  await expect(acknowledgment).toBeChecked();
  await expect(page.getByRole("heading", { name: "Upload first draft" })).toBeVisible();

  await input.setInputFiles(fixture);
  await page.getByRole("button", { name: "Create submission", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Upload revision" })).toBeVisible();
  await expect(page.getByText("Selected asset: Decoded media", { exact: true })).toBeVisible();
  await expect(page.getByText("Measured duration: 2 seconds", { exact: true })).toBeVisible();
  await expect(page.getByText("Dimensions: 320 × 240 pixels", { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: /Fixture scenario/ }).selectOption("clean");
  await page.getByRole("button", { name: "Start Check", exact: true }).click();
  await expect(page.locator(".status-triptych").getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic fixture evidence", { exact: true })).toBeVisible();
  await page.getByRole("region", { name: "Processing authorization", exact: true }).screenshot({ path: testInfo.outputPath("processing-authorization.png") });
  await page.screenshot({ path: testInfo.outputPath("decoded-media.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  await page.getByRole("button", { name: "Withdraw authorization and delete" }).click();
  await expect(page.getByRole("button", { name: "Confirm withdrawal and delete" })).toBeDisabled();
  await page.getByRole("note").filter({ hasText: "Confirm irreversible withdrawal" }).screenshot({ path: testInfo.outputPath("withdrawal-confirmation.png") });
  await page.getByRole("checkbox", { name: /withdrawal cannot reactivate/ }).check();
  await page.getByRole("button", { name: "Confirm withdrawal and delete" }).click();
  await expect(page.getByText("Deletion complete", { exact: true })).toBeVisible();
  await page.reload();
  const history = page.getByRole("region", { name: "Deletion history", exact: true });
  await expect(history.locator("summary").first()).toBeVisible();
  await history.locator("summary").first().click();
  await expect(history.getByText("Supabase Storage — Completed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Vouch" })).toBeVisible();
  expect(errors).toEqual([]);
});
