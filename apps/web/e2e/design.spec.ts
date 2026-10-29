import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";

const WIDTHS = [320, 375, 414, 768, 1280, 1440, 1920];
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);

function observeLocalPage(page: Page) {
  const errors: string[] = [];
  const remoteOrigins = new Set<string>();
  const fontOrigins = new Set<string>();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.protocol.startsWith("http")) return;
    if (!LOOPBACK_HOSTS.has(url.hostname)) remoteOrigins.add(url.origin);
    if (request.resourceType() === "font") fontOrigins.add(url.origin);
  });
  return { errors, remoteOrigins, fontOrigins };
}

async function noDocumentOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    viewport: innerWidth,
    overflowing: [...document.body.querySelectorAll("*")].map((element) => {
      const box = element.getBoundingClientRect();
      return { tag: element.tagName, class: element.getAttribute("class"), left: box.left, right: box.right, width: box.width };
    }).filter((box) => box.width > 0 && (box.right > innerWidth + 1 || box.left < -1)).sort((a, b) => b.width - a.width).slice(0, 8),
  }));
  expect(Math.max(dimensions.document, dimensions.body), JSON.stringify(dimensions)).toBeLessThanOrEqual(dimensions.viewport + 1);
}

async function usableControl(control: Locator, page: Page) {
  await expect(control).toBeVisible();
  const box = await control.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThanOrEqual(44);
  expect(box!.height).toBeGreaterThanOrEqual(44);
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
}

async function visibleKeyboardFocus(control: Locator) {
  await expect(control).toBeFocused();
  expect(await control.evaluate((element) => {
    const style = getComputedStyle(element);
    return element.matches(":focus-visible") && (
      (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0)
      || style.boxShadow !== "none"
    );
  })).toBe(true);
}

async function localFontsLoaded(page: Page) {
  const loaded = await page.evaluate(async () => {
    await document.fonts.ready;
    const requests = [
      '700 32px "Space Grotesk Variable"',
      '400 16px "IBM Plex Sans"',
      '400 14px "IBM Plex Mono"',
    ];
    return Promise.all(requests.map(async (request) => {
      const faces = await document.fonts.load(request, "Vouch 0123456789");
      return faces.length > 0 && faces.every((face) => face.status === "loaded");
    }));
  });
  expect(loaded).toEqual([true, true, true]);
  expect(await page.locator("body").evaluate((element) => getComputedStyle(element).fontFamily)).toContain("IBM Plex Sans");
  expect(await page.locator("h1").first().evaluate((element) => getComputedStyle(element).fontFamily)).toContain("Georgia");
}

async function sampleTextContrast(page: Page, selectors: Array<{ label: string; selector: string }>) {
  return page.evaluate((samples) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) throw new Error("Contrast sampling requires a 2D canvas.");
    function rgba(color: string) {
      context!.clearRect(0, 0, 1, 1);
      context!.fillStyle = color;
      context!.fillRect(0, 0, 1, 1);
      const channels = context!.getImageData(0, 0, 1, 1).data;
      return [channels[0], channels[1], channels[2], channels[3] / 255];
    }
    function composite(front: number[], back: number[]) {
      return [0, 1, 2].map((channel) => front[channel] * front[3] + back[channel] * (1 - front[3])).concat(1);
    }
    function luminance(color: number[]) {
      const linear = color.slice(0, 3).map((channel) => {
        const srgb = channel / 255;
        return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
    }
    const hex = (color: number[]) => `#${color.slice(0, 3).map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
    return samples.map(({ label, selector }) => {
      const element = document.querySelector(selector);
      if (!element) throw new Error(`Contrast sample missing: ${label}`);
      const ancestors: Element[] = [];
      for (let current: Element | null = element; current; current = current.parentElement) ancestors.unshift(current);
      let background = [255, 255, 255, 1];
      for (const ancestor of ancestors) background = composite(rgba(getComputedStyle(ancestor).backgroundColor), background);
      const style = getComputedStyle(element);
      const foreground = composite(rgba(style.color), background);
      const foregroundLuminance = luminance(foreground);
      const backgroundLuminance = luminance(background);
      const ratio = (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05);
      const size = parseFloat(style.fontSize);
      const weight = parseInt(style.fontWeight, 10);
      const minimum = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      return { label, foreground: hex(foreground), background: hex(background), ratio: Math.round(ratio * 100) / 100, minimum };
    });
  }, selectors);
}

async function signInMarketer(page: Page) {
  // Ignored local setup output. Never attach credentials, Auth requests or browser traces.
  const credentials = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../.local/credentials.json"), "utf8")) as { password: string };
  await page.getByLabel("Email", { exact: true }).fill("marketer@vouch.test");
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review pipeline", exact: true })).toBeVisible();
  await expect(page.locator(".campaign-table, .state-panel.empty").first()).toBeVisible();
}

test("Signal sign-in, workspace and campaign stay usable across the accepted widths", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const observed = observeLocalPage(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to Vouch", exact: true })).toBeVisible();
  await localFontsLoaded(page);
  const signInContrast = await sampleTextContrast(page, [
    { label: "Sign-in panel heading", selector: "#sign-in-heading" },
    { label: "Sign-in helper", selector: ".auth-note" },
    { label: "Sign-in lede", selector: ".auth-introduction .lede" },
    { label: "Enabled email input", selector: "#sign-in-email" },
    { label: "Enabled sign-in button", selector: ".auth-form .button.primary" },
  ]);

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await usableControl(page.getByLabel("Email", { exact: true }), page);
    await usableControl(page.getByLabel("Password", { exact: true }), page);
    await usableControl(page.getByRole("button", { name: "Sign in", exact: true }), page);
    await noDocumentOverflow(page);
    if (width === 375 || width === 1440) {
      await page.screenshot({ path: testInfo.outputPath(`signal-sign-in-${width}.png`), fullPage: true });
    }
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  await noDocumentOverflow(page);
  const signInButton = await page.getByRole("button", { name: "Sign in", exact: true }).boundingBox();
  expect(signInButton).not.toBeNull();
  expect(signInButton!.y + signInButton!.height).toBeLessThanOrEqual(800);

  // Start before the form to verify native tab order and the actual keyboard focus indicator.
  await page.getByLabel("Email", { exact: true }).focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await visibleKeyboardFocus(page.getByLabel("Email", { exact: true }));
  await page.keyboard.press("Tab");
  await visibleKeyboardFocus(page.getByLabel("Password", { exact: true }));
  await page.keyboard.press("Tab");
  await visibleKeyboardFocus(page.getByRole("button", { name: "Sign in", exact: true }));

  await signInMarketer(page);
  await localFontsLoaded(page);
  const drawer = page.locator("details.create-drawer");
  if ((await drawer.getAttribute("open")) === null) await drawer.locator("summary").click();
  const workspaceContrast = await sampleTextContrast(page, [
    { label: "Dashboard heading", selector: ".main-content h1" },
    { label: "Dashboard muted lede", selector: ".main-content .lede" },
    { label: "Active navigation", selector: ".nav-link.active" },
    { label: "Enabled campaign action", selector: ".campaign-form .button.primary" },
    { label: "Fixture status", selector: "#campaigns .badge" },
  ]);
  const contrastPath = testInfo.outputPath("signal-text-contrast.json");
  writeFileSync(contrastPath, JSON.stringify([...signInContrast, ...workspaceContrast], null, 2));
  await testInfo.attach("signal-text-contrast", { path: contrastPath, contentType: "application/json" });
  for (const sample of [...signInContrast, ...workspaceContrast]) {
    expect(sample.ratio, JSON.stringify(sample)).toBeGreaterThanOrEqual(sample.minimum);
  }
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await noDocumentOverflow(page);
    await usableControl(page.getByRole("button", { name: "Sign out", exact: true }), page);
    if (width === 375 || width === 1440) {
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath(`signal-workspace-${width}.png`) });
    }
  }

  const campaignName = `Signal layout ${Date.now()}`;
  await page.getByRole("textbox", { name: "Campaign name", exact: true }).fill(campaignName);
  await page.getByRole("button", { name: "Create campaign", exact: true }).click();
  await expect(page.getByRole("heading", { name: campaignName, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create submission", exact: true })).toBeVisible();
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await noDocumentOverflow(page);
    if (width === 375 || width === 1440) {
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath(`signal-campaign-${width}.png`) });
    }
  }
  await page.getByRole("link", { name: "Vouch workspace home", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review pipeline", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: `Open ${campaignName}`, exact: true })).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Search loaded campaigns", exact: true });
  await search.fill(campaignName);
  await expect(page.locator(".campaign-table tbody tr")).toHaveCount(1);
  await expect(page.locator(".workspace-toolbar")).toContainText(/1 of \d+ loaded/);
  await expect(page.getByRole("link", { name: `Open ${campaignName}`, exact: true })).toBeVisible();
  await search.fill(`No campaign matches ${Date.now()}`);
  await expect(page.getByRole("heading", { name: "No matching campaigns", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear search", exact: true }).click();
  await expect(search).toHaveValue("");
  await expect(page.getByRole("link", { name: `Open ${campaignName}`, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Vouch", exact: true })).toBeVisible();

  expect(observed.errors).toEqual([]);
  expect([...observed.remoteOrigins]).toEqual([]);
  expect(observed.fontOrigins.size).toBeGreaterThan(0);
  expect([...observed.fontOrigins].every((origin) => LOOPBACK_HOSTS.has(new URL(origin).hostname))).toBe(true);
});

test("reduced motion keeps the sign-in sculpture static and the form independent", async ({ page }) => {
  const observed = observeLocalPage(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to Vouch", exact: true })).toBeVisible();
  await expect(page.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "static");
  await expect(page.getByTestId("signal-fallback")).toBeVisible();
  await expect(page.getByTestId("signal-sculpture").locator("canvas")).toBeHidden();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
  expect(observed.errors).toEqual([]);
  expect([...observed.remoteOrigins]).toEqual([]);
});

test("unavailable WebGL falls back without blocking authentication", async ({ page }) => {
  const observed = observeLocalPage(page);
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, type: string, ...arguments_: unknown[]) {
      if (["webgl", "webgl2", "experimental-webgl"].includes(type)) return null;
      return Reflect.apply(original, this, [type, ...arguments_]);
    } as typeof original;
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to Vouch", exact: true })).toBeVisible();
  await expect(page.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "unavailable");
  await expect(page.getByTestId("signal-fallback")).toBeVisible();
  await signInMarketer(page);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Vouch", exact: true })).toBeVisible();
  expect(observed.errors).toEqual([]);
  expect([...observed.remoteOrigins]).toEqual([]);
});

test("a live reduced-motion change can return to the original graphics capability", async ({ page }) => {
  const observed = observeLocalPage(page);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const sculpture = page.getByTestId("signal-sculpture");
  await expect(sculpture).toHaveAttribute("data-mode", /^(interactive|paused|unavailable)$/);
  const initialMode = await sculpture.getAttribute("data-mode");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(sculpture).toHaveAttribute("data-mode", "static");
  await expect(page.getByTestId("signal-fallback")).toBeVisible();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(sculpture).toHaveAttribute("data-mode", initialMode === "unavailable" ? "unavailable" : /^(interactive|paused)$/);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
  expect(observed.errors).toEqual([]);
  expect([...observed.remoteOrigins]).toEqual([]);
});
