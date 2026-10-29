"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  errorMessage,
  FIXTURE_IDENTITIES,
  getWorkspaces,
} from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { AUTH_MODE } from "@/lib/supabase";
import { IdentityContext, type IdentityContextValue } from "@/components/identity-state";
import { SupabaseIdentityProvider } from "@/components/supabase-identity";

const STORAGE_KEY = "vouch.fixture-identity";

export function IdentityProvider({ children }: { children: ReactNode }) {
  return AUTH_MODE === "fixture"
    ? <FixtureIdentityProvider>{children}</FixtureIdentityProvider>
    : <SupabaseIdentityProvider>{children}</SupabaseIdentityProvider>;
}

function FixtureIdentityProvider({ children }: { children: ReactNode }) {
  const [identityKey, setIdentityKeyState] = useState(FIXTURE_IDENTITIES[0].key);
  const [workspace, setWorkspace] = useState<Workspace>();
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceError, setWorkspaceError] = useState<string>();
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved && FIXTURE_IDENTITIES.some((candidate) => candidate.key === saved)) {
      queueMicrotask(() => setIdentityKeyState(saved));
    }
  }, []);

  const identity =
    FIXTURE_IDENTITIES.find((candidate) => candidate.key === identityKey) ??
    FIXTURE_IDENTITIES[0];

  const setIdentityKey = useCallback((key: string) => {
    if (!FIXTURE_IDENTITIES.some((candidate) => candidate.key === key)) return;
    setIdentityKeyState(key);
    window.localStorage.setItem(STORAGE_KEY, key);
  }, []);

  const reloadWorkspace = useCallback(() => {
    setReloadToken((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      setWorkspace(undefined);
      setWorkspaceError(undefined);
      setWorkspaceLoading(true);
    });
    void getWorkspaces(identity, controller.signal)
      .then((workspaces) => {
        const selected =
          workspaces.find((item) => item.id === identity.organizationId) ?? workspaces[0];
        if (!selected) {
          setWorkspaceError("This fixture identity has no active workspace membership.");
          return;
        }
        setWorkspace(selected);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setWorkspaceError(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setWorkspaceLoading(false);
      });
    return () => controller.abort();
  }, [identity, reloadToken]);

  const value = useMemo<IdentityContextValue>(
    () => ({
      authMode: "fixture",
      identity,
      setIdentityKey,
      workspace,
      workspaceLoading,
      workspaceError,
      reloadWorkspace,
    }),
    [identity, reloadWorkspace, setIdentityKey, workspace, workspaceError, workspaceLoading],
  );

  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}

export { useIdentity } from "@/components/identity-state";
