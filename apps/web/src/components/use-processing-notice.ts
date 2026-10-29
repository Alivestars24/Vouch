"use client";

import { useCallback, useEffect, useState } from "react";

import { errorMessage, getProcessingNotice } from "@/lib/api";
import type { ProcessingNotice } from "@/lib/types";

export function useProcessingNotice() {
  const [notice, setNotice] = useState<ProcessingNotice>();
  const [acknowledged, setAcknowledged] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const refresh = useCallback(async (signal?: AbortSignal) => {
    setAcknowledged(false);
    setLoading(true);
    setError(undefined);
    try {
      const current = await getProcessingNotice(signal);
      if (!signal?.aborted) setNotice(current);
    } catch (caught) {
      if (!signal?.aborted) {
        setNotice(undefined);
        setError(errorMessage(caught));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => { if (!controller.signal.aborted) void refresh(controller.signal); });
    return () => controller.abort();
  }, [refresh]);
  return { notice, acknowledged, setAcknowledged, loading, error, refresh };
}
