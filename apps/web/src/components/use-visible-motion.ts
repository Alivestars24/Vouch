"use client";

import { useEffect, useState, type RefObject } from "react";

/** Optional graphics fail static unless visibility and motion preferences can be observed. */
export function useVisibleMotion(ref: RefObject<HTMLElement | null>) {
  const [allowed, setAllowed] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof window.matchMedia !== "function" || typeof IntersectionObserver === "undefined") return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!motion || typeof motion.matches !== "boolean" || typeof motion.addEventListener !== "function" || typeof motion.removeEventListener !== "function") return;
    let alive = true;
    let intersecting = false;
    const update = () => {
      if (alive) setAllowed(intersecting && !motion.matches && document.visibilityState !== "hidden");
    };
    const observer = new IntersectionObserver(([entry]) => {
      intersecting = Boolean(entry?.isIntersecting);
      update();
    }, { threshold: 0.01 });
    observer.observe(element);
    motion.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      alive = false;
      observer.disconnect();
      motion.removeEventListener("change", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, [ref]);
  return allowed;
}
