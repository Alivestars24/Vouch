import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

// Generated only by the local provisioning command; never committed or printed.
function localCredentials(): { password: string; users: Array<{ email: string; role: string }> } {
  return JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../.local/credentials.json"), "utf8"));
}

async function signIn(page: Page, email: string, password: string) {
  await expect(page.getByRole("heading", { name: "Sign in to Vouch" })).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("real local sign-in, private upload, partial Check, revision and exact-version approval", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const credentials = localCredentials();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to Vouch" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("sign-in.png"), fullPage: true });
  await signIn(page, "marketer@vouch.test", "incorrect-test-password");
  await expect(page.locator("#sign-in-error")).toContainText("Sign-in failed");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
  await signIn(page, "marketer@vouch.test", credentials.password);
  await expect(page.getByRole("heading", { name: "Review pipeline" })).toBeVisible();
  await expect(page.locator(".campaign-table, .state-panel.empty").first()).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Fixture identity" })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Workspace", exact: true })).toHaveValue("11111111-1111-4111-8111-111111111111");
  const drawer = page.locator("details.create-drawer");
  if ((await drawer.getAttribute("open")) === null) await drawer.locator("summary").click();
  const name = `Authenticated browser ${Date.now()}`;
  await page.getByRole("textbox", { name: "Campaign name" }).fill(name);
  await page.getByRole("button", { name: "Create campaign", exact: true }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText("Fixture media processing", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Use synthetic MP4" }).click();
  await page.getByRole("textbox", { name: "Caption snapshot" }).fill("Authorized private launch draft.");
  await page.getByRole("checkbox", { name: /authorized to upload/ }).check();
  await page.getByRole("checkbox", { name: /I acknowledge the processing notice/ }).check();
  const uploaded = page.waitForRequest((request) => request.method() === "PUT" && request.url().includes("/uploads/"));
  await page.getByRole("button", { name: "Create submission", exact: true }).click();
  const upload = await uploaded;
  expect(upload.headers()["authorization"]).toMatch(/^Bearer /);
  expect(upload.headers()["x-fixture-user"]).toBeUndefined();
  await expect(page.getByRole("heading", { name: "Upload revision" })).toBeVisible();
  const download = await page.request.get(upload.url(), { headers: {
    Authorization: upload.headers()["authorization"],
    "X-Organization-Id": upload.headers()["x-organization-id"],
  } });
  expect(download.status()).toBe(200);
  expect((await download.body()).byteLength).toBeGreaterThan(20);

  await page.getByRole("combobox", { name: /Fixture scenario/ }).selectOption("partial_voice");
  await page.getByRole("button", { name: "Start Check", exact: true }).click();
  await expect(page.getByText("Evidence is incomplete", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic fixture evidence", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeDisabled();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "reviewer@vouch.test", credentials.password);
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeEnabled();
  const accepted = page.getByRole("button", { name: "Accepted", exact: true }).first();
  if (await accepted.count()) {
    await accepted.click();
    await expect(page.getByText("Recorded: Accepted", { exact: true }).first()).toBeVisible();
  }
  await page.getByRole("button", { name: "Approve exact version" }).click();
  await expect(page.getByText(/Approval is blocked: analysis_not_complete/)).toBeVisible();

  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "marketer@vouch.test", credentials.password);
  await page.getByRole("button", { name: "Use synthetic MP4" }).click();
  await page.getByRole("textbox", { name: "Caption snapshot" }).fill("Revised authorized private draft.");
  await page.getByRole("checkbox", { name: /authorized to upload/ }).check();
  await page.getByRole("checkbox", { name: /I acknowledge the processing notice/ }).check();
  await page.getByRole("button", { name: "Create revision", exact: true }).click();
  await expect(page.getByText("Next: v3", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Three states, kept separate" })).toHaveCount(0);
  await page.getByRole("combobox", { name: /Fixture scenario/ }).selectOption("clean");
  await page.getByRole("button", { name: "Start Check", exact: true }).click();
  await expect(page.locator(".status-triptych").getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No findings in observed coverage" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "reviewer@vouch.test", credentials.password);
  await page.getByRole("button", { name: "Approve exact version" }).click();
  await expect(page.getByText("Human approval recorded", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("approved-version.png"), fullPage: true });
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeDisabled();
  await page.getByRole("button", { name: "Compare with previous Check" }).click();
  await expect(page.getByText("Resolved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "marketer@vouch.test", credentials.password);
  await page.getByRole("button", { name: "Delete submission data" }).click();
  await expect(page.getByText("Deletion complete", { exact: true })).toBeVisible();
  await expect(page.getByText(/Supabase Storage: Completed/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Deletion history", exact: true })).toBeVisible();
  const history = page.getByRole("region", { name: "Deletion history", exact: true });
  await history.locator("summary").first().click();
  await expect(history.getByText("Completed", { exact: true })).toBeVisible();
  await expect(history.getByText("Supabase Storage — Completed", { exact: true })).toBeVisible();
  await expect(history.getByRole("button", { name: "Retry cleanup", exact: true })).toHaveCount(0);
  await history.screenshot({ path: testInfo.outputPath("deletion-history.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Vouch" })).toBeVisible();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("a signed-in user with revoked membership cannot open the workspace", async ({ page }) => {
  const credentials = localCredentials();
  await page.goto("/");
  await signIn(page, "revoked@vouch.test", credentials.password);
  await expect(page.getByRole("heading", { name: "No active workspace membership" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Review pipeline" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Create campaign", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Vouch" })).toBeVisible();
});

test("sign-in remains usable at narrow, tablet and desktop widths", async ({ page }, testInfo) => {
  await page.goto("/");
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("heading", { name: "Sign in to Vouch" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`sign-in-${width}.png`), fullPage: true });
  }
  await page.getByLabel("Email", { exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeFocused();
});
