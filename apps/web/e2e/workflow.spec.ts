import { expect, test } from "@playwright/test";

test("authorized draft, partial evidence, revision, and exact-version approval", async ({ page }) => {
  test.setTimeout(60_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Review pipeline" })).toBeVisible();
  await expect(page.locator(".campaign-table, .state-panel.empty").first()).toBeVisible();
  const drawer = page.locator("details.create-drawer");
  if ((await drawer.getAttribute("open")) === null) {
    await drawer.locator("summary").click();
  }
  const name = `Fixture browser ${Date.now()}`;
  await page.getByRole("textbox", { name: "Campaign name" }).fill(name);
  await page.getByRole("button", { name: "Create campaign", exact: true }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText("Fixture media processing", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Use synthetic MP4" }).click();
  await page.getByRole("textbox", { name: "Caption snapshot" }).fill("Authorized launch draft.");
  const rights = page.getByRole("checkbox", { name: /authorized to upload/ });
  await rights.check();
  await page.getByRole("checkbox", { name: /I acknowledge the processing notice/ }).check();
  await page.getByRole("button", { name: "Create submission", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Upload revision" })).toBeVisible();

  await page.getByRole("combobox", { name: /Fixture scenario/ }).selectOption("partial_voice");
  await page.getByRole("button", { name: "Start Check", exact: true }).click();
  await expect(page.getByText("Evidence is incomplete", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic fixture evidence", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeDisabled();

  const identity = page.getByRole("combobox", { name: /Fixture identity/ });
  await identity.selectOption("acme-reviewer");
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve exact version" }).click();
  await expect(page.getByText(/Approval is blocked: analysis_not_complete/)).toBeVisible();

  await identity.selectOption("acme-marketer");
  await page.getByRole("button", { name: "Use synthetic MP4" }).click();
  await page.getByRole("textbox", { name: "Caption snapshot" }).fill("Revised authorized draft.");
  await rights.check();
  await page.getByRole("checkbox", { name: /I acknowledge the processing notice/ }).check();
  await page.getByRole("button", { name: "Create revision", exact: true }).click();
  await expect(page.getByText("Next: v3", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Three states, kept separate" })).toHaveCount(0);

  await page.getByRole("combobox", { name: /Fixture scenario/ }).selectOption("clean");
  await page.getByRole("button", { name: "Start Check", exact: true }).click();
  await expect(page.locator(".status-triptych").getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No findings in observed coverage" })).toBeVisible();
  await identity.selectOption("acme-reviewer");
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeEnabled();
  await page.getByRole("button", { name: "Approve exact version" }).click();
  await expect(page.getByText("Human approval recorded", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve exact version" })).toBeDisabled();
  await page.getByRole("button", { name: "Compare with previous Check" }).click();
  await expect(page.getByText("Resolved", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Withdraw authorization and delete" })).toHaveCount(0);
  await identity.selectOption("acme-marketer");
  await page.getByRole("button", { name: "Withdraw authorization and delete" }).click();
  await expect(page.getByRole("button", { name: "Confirm withdrawal and delete" })).toBeDisabled();
  await page.getByRole("checkbox", { name: /withdrawal cannot reactivate/ }).check();
  await page.getByRole("button", { name: "Confirm withdrawal and delete" }).click();
  await expect(page.getByText("Deletion complete", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
