"use client";

import { BorderBeam } from "border-beam";
import { useEffect, useRef, useState } from "react";
import { ThinkingOrb } from "thinking-orbs";

import { useVisibleMotion } from "@/components/use-visible-motion";

import styles from "./signal-motion.module.css";

/** The package layer is separate from content: suspension never remounts the sculpture. */
export function SignalBeam({ enabled }: { enabled: boolean }) {
  return <div className={styles.beamFrame} aria-hidden="true">{enabled ? <BeamSession /> : null}</div>;
}

function BeamSession() {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useVisibleMotion(ref);
  const remaining = useRef(3200);
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    if (!visible || expired) return;
    const start = performance.now();
    const timeout = window.setTimeout(() => { remaining.current = 0; setExpired(true); }, remaining.current);
    return () => {
      window.clearTimeout(timeout);
      remaining.current = Math.max(0, remaining.current - (performance.now() - start));
    };
  }, [visible, expired]);
  return (
    <div ref={ref} className={styles.beamLayer} data-testid="signal-beam" data-motion={visible && !expired ? "active" : "static"}>
      {visible && !expired ? (
        <BorderBeam className={styles.beam} size="md" theme="dark" colorVariant="mono" staticColors
          strength={0.36} glowSize={0.45} duration={3.2} borderRadius={12}>
          <div className={styles.beamContent} />
        </BorderBeam>
      ) : null}
    </div>
  );
}

/** Animation indicates only a real pending state, never inferred model thought or completion. */
export function SignalActivity({ status, size = 20 }: { status: string; size?: 20 | 64 }) {
  return ["loading", "queued", "running"].includes(status) ? <ActivityGlyph status={status} size={size} /> : null;
}

function ActivityGlyph({ status, size }: { status: string; size: 20 | 64 }) {
  const ref = useRef<HTMLSpanElement>(null);
  const allowed = useVisibleMotion(ref);
  const [paused, setPaused] = useState(false);
  const animate = allowed && !paused;
  return (
    <span ref={ref} className={styles.activity} data-testid="signal-activity" data-status={status} data-motion={animate ? "active" : "static"}>
      <span className={styles.glyph} style={{ width: size, height: size }} aria-hidden="true">
        {animate ? <ThinkingOrb state="working" size={size} theme="light" speed={0.65} gravity={false} aria-hidden="true" /> : <span className={styles.staticOrb} />}
      </span>
      {allowed ? (
        <button type="button" className={styles.pause} aria-label={paused ? "Resume loading animation" : "Pause loading animation"}
          aria-pressed={paused} onClick={() => setPaused(!paused)}>
          <span aria-hidden="true">{paused ? "▷" : "Ⅱ"}</span>
        </button>
      ) : null}
    </span>
  );
}
