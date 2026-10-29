import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SignalActivity, SignalBeam } from "@/components/signal-motion";

vi.mock("border-beam", () => ({
  BorderBeam: ({ children }: { children: React.ReactNode }) => <div data-testid="border-beam">{children}</div>,
}));
vi.mock("thinking-orbs", () => ({
  ThinkingOrb: ({ state }: { state: string }) => <span data-testid="thinking-orb" data-state={state} />,
}));

type ObserverHarness = {
  callback: IntersectionObserverCallback;
  disconnect: ReturnType<typeof vi.fn>;
  targets: Set<Element>;
};

let motion: MediaQueryList;
const intersections: ObserverHarness[] = [];

function observerFor(target: Element) {
  const observer = [...intersections].reverse().find((candidate) => candidate.targets.has(target));
  if (!observer) throw new Error("No IntersectionObserver owns the requested target.");
  return observer;
}

function intersect(target: Element, visible: boolean) {
  const observer = observerFor(target);
  act(() => observer.callback(
    [{ isIntersecting: visible, target }] as IntersectionObserverEntry[],
    {} as IntersectionObserver,
  ));
}

beforeEach(() => {
  intersections.length = 0;
  motion = Object.assign(
    new EventTarget(),
    { matches: false, media: "(prefers-reduced-motion: reduce)", onchange: null },
  ) as MediaQueryList;
  vi.stubGlobal("matchMedia", vi.fn(() => motion));
  vi.stubGlobal("IntersectionObserver", class {
    disconnect = vi.fn();
    targets = new Set<Element>();
    observe = vi.fn((target: Element) => this.targets.add(target));
    constructor(public callback: IntersectionObserverCallback) { intersections.push(this); }
  });
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Signal motion", () => {
  it("bounds the public beam and suspends it when its layer is not visible", () => {
    vi.useFakeTimers();
    const view = render(<SignalBeam enabled />);
    const layer = screen.getByTestId("signal-beam");
    const observer = observerFor(layer);

    expect(layer).toHaveAttribute("data-motion", "static");
    expect(screen.queryByTestId("border-beam")).not.toBeInTheDocument();
    intersect(layer, true);
    expect(layer).toHaveAttribute("data-motion", "active");
    expect(screen.getByTestId("border-beam")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1600));
    intersect(layer, false);
    expect(layer).toHaveAttribute("data-motion", "static");
    act(() => vi.advanceTimersByTime(1600));
    intersect(layer, true);
    act(() => vi.advanceTimersByTime(1600));
    expect(layer).toHaveAttribute("data-motion", "static");
    expect(screen.queryByTestId("border-beam")).not.toBeInTheDocument();

    view.unmount();
    expect(observer.disconnect).toHaveBeenCalledOnce();
  });

  it("shows activity only for real pending states and lets the user pause it", () => {
    const view = render(<SignalActivity status="running" />);
    const activity = screen.getByTestId("signal-activity");
    const observer = observerFor(activity);

    expect(activity).toHaveAttribute("data-motion", "static");
    intersect(activity, true);
    expect(activity).toHaveAttribute("data-motion", "active");
    expect(screen.getByTestId("thinking-orb")).toHaveAttribute("data-state", "working");

    fireEvent.click(screen.getByRole("button", { name: "Pause loading animation" }));
    expect(activity).toHaveAttribute("data-motion", "static");
    fireEvent.click(screen.getByRole("button", { name: "Resume loading animation" }));
    expect(activity).toHaveAttribute("data-motion", "active");

    view.rerender(<SignalActivity status="completed" />);
    expect(screen.queryByTestId("signal-activity")).not.toBeInTheDocument();
    expect(observer.disconnect).toHaveBeenCalledOnce();
  });

  it("fails static for reduced motion and document visibility changes", () => {
    render(<SignalActivity status="queued" />);
    const activity = screen.getByTestId("signal-activity");
    intersect(activity, true);
    expect(activity).toHaveAttribute("data-motion", "active");

    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    fireEvent(document, new Event("visibilitychange"));
    expect(activity).toHaveAttribute("data-motion", "static");

    vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
    Object.defineProperty(motion, "matches", { value: true, configurable: true });
    act(() => motion.dispatchEvent(new Event("change")));
    expect(activity).toHaveAttribute("data-motion", "static");
    expect(screen.queryByRole("button", { name: /loading animation/i })).not.toBeInTheDocument();
  });
});
