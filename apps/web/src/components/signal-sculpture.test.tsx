import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SignalSculpture } from "@/components/signal-sculpture";

const { createRenderer, draw, dispose } = vi.hoisted(() => ({ createRenderer: vi.fn(), draw: vi.fn(), dispose: vi.fn() }));
vi.mock("@/lib/signal-webgl", () => ({ createSignalRenderer: createRenderer }));

let motion: MediaQueryList;
let frameId: number;
let frames: Map<number, FrameRequestCallback>;
const intersections: Array<{
  callback: IntersectionObserverCallback;
  disconnect: ReturnType<typeof vi.fn>;
  targets: Set<Element>;
}> = [];
const resizes: Array<{ disconnect: ReturnType<typeof vi.fn> }> = [];

function observerFor(target: Element) {
  const observer = [...intersections].reverse().find((candidate) => candidate.targets.has(target));
  if (!observer) throw new Error("No IntersectionObserver owns the requested target.");
  return observer;
}
function sculptureCanvas() {
  const canvas = screen.getByTestId("signal-sculpture").querySelector("canvas");
  if (!canvas) throw new Error("Signal sculpture canvas is missing.");
  return canvas;
}
function intersect(target: Element, visible: boolean) {
  const observer = observerFor(target);
  act(() => observer.callback([{ isIntersecting: visible, target }] as IntersectionObserverEntry[], {} as IntersectionObserver));
}
function advanceFrame(time: number) {
  act(() => {
    const next = [...frames.entries()]; frames.clear();
    for (const [, callback] of next) callback(time);
  });
}
async function ready() {
  const view = render(<SignalSculpture />);
  await waitFor(() => expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "interactive"));
  intersect(sculptureCanvas(), true);
  return view;
}

beforeEach(() => {
  vi.clearAllMocks(); intersections.length = 0; resizes.length = 0;
  frameId = 0; frames = new Map();
  motion = Object.assign(new EventTarget(), { matches: false, media: "(prefers-reduced-motion: reduce)", onchange: null }) as MediaQueryList;
  vi.stubGlobal("matchMedia", vi.fn(() => motion));
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => { frames.set(++frameId, callback); return frameId; }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn((id: number) => frames.delete(id)));
  vi.stubGlobal("IntersectionObserver", class {
    disconnect = vi.fn();
    targets = new Set<Element>();
    observe = vi.fn((target: Element) => this.targets.add(target));
    constructor(public callback: IntersectionObserverCallback) { intersections.push(this); }
  });
  vi.stubGlobal("ResizeObserver", class {
    disconnect = vi.fn(); observe = vi.fn();
    constructor() { resizes.push(this); }
  });
  vi.spyOn(performance, "now").mockReturnValue(0);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  createRenderer.mockReturnValue({ draw, dispose });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("public decorative Signal sculpture", () => {
  it("remains static without optional browser graphics APIs", async () => {
    vi.stubGlobal("matchMedia", undefined);
    render(<SignalSculpture />);
    await act(async () => {});
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "static");
    expect(screen.getByTestId("signal-fallback")).toBeVisible();
    expect(createRenderer).not.toHaveBeenCalled();
  });

  it("remains static for a partial legacy MediaQueryList without subscription methods", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addListener: vi.fn(), removeListener: vi.fn() })));
    render(<SignalSculpture />);
    await act(async () => {});
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "static");
    expect(screen.getByTestId("signal-fallback")).toBeVisible();
    expect(createRenderer).not.toHaveBeenCalled();
  });

  it("uses meaningful SVG and no GPU when reduced motion is requested", async () => {
    Object.defineProperty(motion, "matches", { value: true });
    render(<SignalSculpture />);
    await act(async () => {});
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "static");
    expect(screen.getByRole("img", { name: "Vouch folded ribbon mark" })).toBeVisible();
    expect(createRenderer).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Rotate sculpture left" })).toBeDisabled();
  });

  it("keeps the SVG and usable page when WebGL is unavailable", async () => {
    createRenderer.mockReturnValue(null);
    render(<SignalSculpture />);
    await waitFor(() => expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "unavailable"));
    expect(screen.getByTestId("signal-fallback")).toBeVisible();
    expect(frames.size).toBe(0);
  });

  it("caps draws to 30fps, settles after a finite pass and exposes keyboard controls", async () => {
    const user = userEvent.setup();
    await ready();
    advanceFrame(0); advanceFrame(10);
    expect(draw).toHaveBeenCalledTimes(1);
    advanceFrame(34);
    expect(draw).toHaveBeenCalledTimes(2);
    advanceFrame(3300);
    expect(frames.size).toBe(0);
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "paused");
    const rotate = screen.getByRole("button", { name: "Rotate sculpture right" });
    rotate.focus(); await user.keyboard("{Enter}");
    advanceFrame(3400);
    expect(draw.mock.calls.at(-1)![1]).toBeGreaterThan(draw.mock.calls[0][1]);
    await user.click(screen.getByRole("button", { name: "Play sculpture motion" }));
    expect(screen.getByRole("button", { name: "Pause sculpture motion" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Pause sculpture motion" }));
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "paused");
  });

  it("suspends offscreen/hidden work and removes graphics, listeners and observers on unmount", async () => {
    const view = await ready();
    advanceFrame(0);
    const canvas = sculptureCanvas();
    const canvasObserver = observerFor(canvas);
    intersect(canvas, false);
    expect(frames.size).toBe(0);
    intersect(canvas, true);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    fireEvent(document, new Event("visibilitychange"));
    expect(frames.size).toBe(0);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    fireEvent(document, new Event("visibilitychange"));
    expect(frames.size).toBe(1);
    const removeWindow = vi.spyOn(window, "removeEventListener");
    const removeDocument = vi.spyOn(document, "removeEventListener");
    const removeCanvas = vi.spyOn(canvas, "removeEventListener");
    view.unmount();
    expect(dispose).toHaveBeenCalledTimes(1);
    expect(canvasObserver.disconnect).toHaveBeenCalledOnce();
    expect(resizes[0].disconnect).toHaveBeenCalledOnce();
    expect(removeWindow).toHaveBeenCalledWith("resize", expect.any(Function));
    expect(removeDocument).toHaveBeenCalledWith("visibilitychange", expect.any(Function));
    expect(removeCanvas).toHaveBeenCalledWith("pointermove", expect.any(Function));
    expect(removeCanvas).toHaveBeenCalledWith("webglcontextlost", expect.any(Function));
    expect(frames.size).toBe(0);
  });

  it("falls back after context loss without restarting a GPU animation", async () => {
    const view = await ready();
    fireEvent(view.container.querySelector("canvas")!, new Event("webglcontextlost"));
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "unavailable");
    expect(screen.getByTestId("signal-fallback")).toBeVisible();
    expect(dispose).toHaveBeenCalledTimes(1);
    expect(frames.size).toBe(0);
    view.unmount();
    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("allows direct pointer rotation and stops GPU use if reduced-motion preference changes", async () => {
    const view = await ready();
    advanceFrame(0);
    const yaw = draw.mock.calls.at(-1)![1];
    const canvas = view.container.querySelector("canvas")!;
    fireEvent(canvas, Object.assign(new Event("pointerdown"), { pointerId: 1, pointerType: "touch", clientX: 10, clientY: 10 }));
    fireEvent(canvas, Object.assign(new Event("pointermove"), { pointerId: 1, clientX: 50, clientY: 15 }));
    advanceFrame(40);
    expect(draw.mock.calls.at(-1)![1]).toBeGreaterThan(yaw);
    act(() => {
      Object.defineProperty(motion, "matches", { value: true });
      motion.dispatchEvent(new Event("change"));
    });
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "static");
    expect(screen.getByTestId("signal-fallback")).toBeVisible();
    expect(dispose).toHaveBeenCalledTimes(1);
    expect(frames.size).toBe(0);
  });

  it("survives React Strict Mode setup-cleanup-setup without a leaked renderer", async () => {
    const view = render(<StrictMode><SignalSculpture /></StrictMode>);
    await waitFor(() => expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "interactive"));
    expect(createRenderer).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(dispose).toHaveBeenCalledTimes(1);
    expect(frames.size).toBe(0);
  });

  it("reinitializes and draws after reduced motion is enabled then disabled", async () => {
    await ready();
    advanceFrame(0);
    act(() => {
      Object.defineProperty(motion, "matches", { value: true, configurable: true });
      motion.dispatchEvent(new Event("change"));
    });
    expect(dispose).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "static");
    act(() => {
      Object.defineProperty(motion, "matches", { value: false, configurable: true });
      motion.dispatchEvent(new Event("change"));
    });
    expect(createRenderer).toHaveBeenCalledTimes(2);
    intersect(sculptureCanvas(), true);
    advanceFrame(50);
    expect(draw).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("signal-sculpture")).toHaveAttribute("data-mode", "interactive");
  });
});
