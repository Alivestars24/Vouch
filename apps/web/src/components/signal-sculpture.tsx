"use client";

import { useEffect, useId, useRef, useState } from "react";

import { SignalBeam } from "@/components/signal-motion";
import { createSignalRenderer, type SignalPalette } from "@/lib/signal-webgl";

type Mode = "interactive" | "paused" | "static" | "unavailable";
type Controls = { rotate(direction: number): void; play(): void; pause(): void };

function palette(element: HTMLElement): SignalPalette {
  const styles = getComputedStyle(element);
  const channels = (name: string): [number, number, number] => {
    const values = styles.getPropertyValue(name).trim().split(/\s+/).map(Number);
    return values.length === 3 && values.every((value) => Number.isFinite(value) && value >= 0 && value <= 1)
      ? [values[0], values[1], values[2]] : [0.75, 0.75, 0.75];
  };
  return { accent: channels("--signal-accent-rgb"), metal: channels("--signal-metal-rgb") };
}

/** Decorative public brand graphic only. Sign-in never waits for this component. */
export function SignalSculpture() {
  const gradient = useId().replaceAll(":", "");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controls = useRef<Controls | null>(null);
  const [mode, setMode] = useState<Mode>("static");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (typeof window.matchMedia !== "function" || typeof requestAnimationFrame !== "function" || typeof cancelAnimationFrame !== "function") return;
    let disposed = false;
    let stopGraphics = () => {};
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    // A partial/legacy MediaQueryList must not make optional graphics break sign-in.
    if (!motion || typeof motion.matches !== "boolean" || typeof motion.addEventListener !== "function" || typeof motion.removeEventListener !== "function") return;

    function start() {
      stopGraphics();
      controls.current = null;
      if (disposed || !canvas) return;
      if (motion.matches) { setMode("static"); return; }
      if (typeof IntersectionObserver === "undefined") { setMode("unavailable"); return; }
      const renderer = createSignalRenderer(canvas, palette(canvas));
      if (!renderer) { setMode("unavailable"); return; }
      let alive = true;
      let frame = 0;
      let lastDraw = -Infinity;
      let deadline = performance.now() + 3200;
      let visible = document.visibilityState !== "hidden";
      let intersecting = false;
      let dirty = true;
      let pitch = -0.33;
      let yaw = -0.5;
      let paused = false;
      let scrollPitch = 0;
      let scrollYaw = 0;
      let dragging: { x: number; y: number; id: number } | undefined;
      const cancel = () => { if (frame) cancelAnimationFrame(frame); frame = 0; };
      const schedule = () => {
        if (alive && visible && intersecting && !frame && (dirty || deadline > 0)) frame = requestAnimationFrame(draw);
      };
      function draw(now: number) {
        frame = 0;
        if (!alive || !visible || !intersecting) return;
        if (now - lastDraw < 1000 / 30) { schedule(); return; }
        const moving = deadline > now;
        if (moving) yaw += Math.min(Number.isFinite(lastDraw) ? now - lastDraw : 0, 80) * 0.0003;
        else if (deadline > 0) {
          deadline = 0;
          paused = true;
          setMode("paused");
        }
        renderer!.draw(pitch + scrollPitch, yaw + scrollYaw);
        lastDraw = now;
        dirty = false;
        if (moving) schedule();
      }
      const settle = () => { deadline = 0; cancel(); };
      const pause = () => { paused = true; settle(); setMode("paused"); dirty = true; schedule(); };
      controls.current = {
        rotate(direction) { settle(); yaw += direction * 0.26; dirty = true; schedule(); },
        pause,
        play() { paused = false; deadline = performance.now() + 3200; dirty = true; setMode("interactive"); schedule(); },
      };
      // Passive, input-driven rendering; no scroll hijack or idle animation loop.
      const onScroll = () => {
        if (!alive || paused || !visible || !intersecting) return;
        const bounds = canvas.getBoundingClientRect();
        const progress = Math.max(-1, Math.min(1, (window.innerHeight / 2 - bounds.top - bounds.height / 2) / Math.max(window.innerHeight, 1)));
        scrollPitch = progress * 0.48;
        scrollYaw = progress * 0.72;
        dirty = true; schedule();
      };
      const onVisibility = () => { visible = document.visibilityState !== "hidden"; if (visible) { dirty = true; schedule(); } else cancel(); };
      const onResize = () => { dirty = true; schedule(); };
      const onPointerDown = (event: PointerEvent) => {
        if (!alive || (event.pointerType === "mouse" && event.button !== 0)) return;
        settle();
        dragging = { x: event.clientX, y: event.clientY, id: event.pointerId };
        canvas.setPointerCapture?.(event.pointerId);
      };
      const onPointerMove = (event: PointerEvent) => {
        if (!dragging || event.pointerId !== dragging.id) return;
        yaw += (event.clientX - dragging.x) * 0.008;
        pitch = Math.max(-1.1, Math.min(1.1, pitch + (event.clientY - dragging.y) * 0.006));
        dragging = { x: event.clientX, y: event.clientY, id: event.pointerId };
        dirty = true; schedule();
      };
      const onPointerEnd = (event: PointerEvent) => {
        if (dragging?.id !== event.pointerId) return;
        dragging = undefined;
        if (canvas.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      };
      const onContextLost = () => { stopGraphics(); if (!disposed) setMode("unavailable"); };
      const intersection = new IntersectionObserver(([entry]) => {
        intersecting = Boolean(entry?.isIntersecting);
        if (intersecting) { dirty = true; schedule(); } else cancel();
      }, { threshold: 0.01 });
      intersection.observe(canvas);
      const resize = typeof ResizeObserver !== "undefined" ? new ResizeObserver(onResize) : undefined;
      resize?.observe(canvas);
      window.addEventListener("resize", onResize);
      window.addEventListener("scroll", onScroll, { passive: true });
      document.addEventListener("visibilitychange", onVisibility);
      canvas.addEventListener("pointerdown", onPointerDown);
      canvas.addEventListener("pointermove", onPointerMove);
      canvas.addEventListener("pointerup", onPointerEnd);
      canvas.addEventListener("pointercancel", onPointerEnd);
      canvas.addEventListener("webglcontextlost", onContextLost);
      stopGraphics = () => {
        if (!alive) return;
        alive = false; cancel(); controls.current = null;
        if (dragging && canvas.hasPointerCapture?.(dragging.id)) canvas.releasePointerCapture(dragging.id);
        dragging = undefined;
        intersection.disconnect(); resize?.disconnect();
        window.removeEventListener("resize", onResize);
        window.removeEventListener("scroll", onScroll);
        document.removeEventListener("visibilitychange", onVisibility);
        canvas.removeEventListener("pointerdown", onPointerDown);
        canvas.removeEventListener("pointermove", onPointerMove);
        canvas.removeEventListener("pointerup", onPointerEnd);
        canvas.removeEventListener("pointercancel", onPointerEnd);
        canvas.removeEventListener("webglcontextlost", onContextLost);
        renderer.dispose();
      };
      setMode("interactive");
    }
    motion.addEventListener("change", start);
    queueMicrotask(start);
    return () => { disposed = true; motion.removeEventListener("change", start); stopGraphics(); };
  }, []);

  const available = mode === "interactive" || mode === "paused";
  return (
    <div className="signal-sculpture" data-testid="signal-sculpture" data-mode={mode}>
      <SignalBeam enabled={mode === "interactive"} />
      <canvas ref={canvasRef} className="signal-sculpture-canvas" hidden={!available} aria-hidden="true" />
      <div className="signal-sculpture-fallback" hidden={available}>
      <svg data-testid="signal-fallback" viewBox="0 0 300 300" width="100%" height="100%" role="img" aria-label="Vouch folded ribbon mark">
        <defs><linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--color-surface)" /><stop offset=".48" stopColor="var(--color-muted)" /><stop offset=".65" stopColor="var(--color-surface)" /><stop offset="1" stopColor="var(--color-ink)" /></linearGradient></defs>
        <path fill={`url(#${gradient})`} fillRule="evenodd" d="M103 42C126 17 156 18 179 40L255 118C278 142 276 174 250 194L173 252C150 269 123 263 108 242L48 161C30 136 42 105 61 85Zm17 43L91 116C81 126 78 136 86 148L135 215C140 222 148 223 156 217L220 168C229 161 231 153 222 144L156 77C146 67 132 69 120 85Z" />
        <path fill="var(--color-accent)" d="m103 42 17 43c12-16 26-18 36-8l66 67c9 9 7 17-2 24l30 26c26-20 28-52 5-76l-76-78c-23-22-53-23-76 2Z" />
        <path fill="var(--color-ink)" opacity=".3" d="m108 242 27-27c5 7 13 8 21 2l64-49 30 26-77 58c-23 17-50 11-65-10Z" />
      </svg>
      </div>
      <div className="signal-sculpture-controls" aria-label="Decorative sculpture controls">
        <button type="button" disabled={!available} aria-label="Rotate sculpture left" onClick={() => controls.current?.rotate(-1)}>↶</button>
        <button type="button" disabled={!available} onClick={() => mode === "interactive" ? controls.current?.pause() : controls.current?.play()}>
          {mode === "interactive" ? "Pause sculpture motion" : "Play sculpture motion"}
        </button>
        <button type="button" disabled={!available} aria-label="Rotate sculpture right" onClick={() => controls.current?.rotate(1)}>↷</button>
      </div>
      <span className="sr-only">Decorative brand graphic, not an analysis or progress indicator.</span>
    </div>
  );
}
