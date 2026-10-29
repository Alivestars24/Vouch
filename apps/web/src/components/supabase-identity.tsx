"use client";

import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { IdentityContext, type IdentityContextValue } from "@/components/identity-state";
import { ApiError, errorMessage, getWorkspaces } from "@/lib/api";
import { getSupabaseClient, GOOGLE_OAUTH_ENABLED, SESSION_EXPIRED_EVENT } from "@/lib/supabase";
import { startGoogleSignIn } from "@/lib/google-oauth";
import type { FixtureIdentity, Workspace } from "@/lib/types";

export function SupabaseIdentityProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>();
  const [authError, setAuthError] = useState<string>();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [workspacesResolved, setWorkspacesResolved] = useState(false);
  const [workspaceError, setWorkspaceError] = useState<string>();
  const [reloadToken, setReloadToken] = useState(0);
  const tokenRef = useRef<string | undefined>(undefined);
  const subjectRef = useRef<string | undefined>(undefined);

  const clearPrivateState = useCallback(() => {
    setWorkspaces([]);
    setOrganizationId("");
    setWorkspaceError(undefined);
    setWorkspaceLoading(false);
    setWorkspacesResolved(false);
  }, []);

  useEffect(() => {
    try {
      const client = getSupabaseClient();
      const { data: { subscription } } = client.auth.onAuthStateChange((_event, next) => {
        tokenRef.current = next?.access_token;
        if (subjectRef.current !== next?.user.id || !next) clearPrivateState();
        subjectRef.current = next?.user.id;
        setSession(next);
      });
      return () => subscription.unsubscribe();
    } catch {
      queueMicrotask(() => {
        setAuthError("Authentication is not configured. Ask your administrator to check the Supabase URL, publishable key and authentication mode.");
        setSession(null);
      });
    }
  }, [clearPrivateState]);

  const signOut = useCallback(async () => {
    tokenRef.current = undefined;
    setSession(null);
    clearPrivateState();
    try {
      const { error } = await getSupabaseClient().auth.signOut({ scope: "local" });
      if (error) throw error;
    } catch {
      setAuthError("Your workspace is closed. Session revocation could not be confirmed; reconnect and sign out again.");
    }
  }, [clearPrivateState]);

  useEffect(() => {
    const expired = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== tokenRef.current) return;
      setAuthError("Your session could not be verified. Sign in again to continue.");
      void signOut().catch(() => setAuthError("Your workspace is closed. Reconnect and sign in again."));
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  }, [signOut]);

  const signIn = useCallback(async (email: string, password: string) => {
    setAuthError(undefined);
    try {
      const { error } = await getSupabaseClient().auth.signInWithPassword({ email, password });
      if (error) throw new Error("Sign-in failed. Check your email and password, or contact your workspace administrator.");
    } catch {
      throw new Error("Sign-in failed. Check your email and password, or contact your workspace administrator.");
    }
  }, []);

  const signInWithGoogle = useCallback(async () => {
    setAuthError(undefined);
    await startGoogleSignIn();
  }, []);

  // Session values transport credentials only; the API resolves every membership and role.
  const discoveryIdentity = useMemo<FixtureIdentity>(() => ({
    key: session?.user.id ?? "signed-out",
    label: session?.user.email ?? "Signed out",
    hint: "Supabase authenticated session",
    user: session?.user.email ?? "",
    organizationId: "",
    organizationLabel: "Select a workspace",
    accessToken: session?.access_token,
  }), [session?.access_token, session?.user.email, session?.user.id]);

  useEffect(() => {
    if (!discoveryIdentity.accessToken) return;
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setWorkspaceLoading(true);
      setWorkspaceError(undefined);
    });
    void getWorkspaces(discoveryIdentity, controller.signal).then((rows) => {
      if (controller.signal.aborted) return;
      setWorkspaces(rows);
      setOrganizationId((current) => rows.some((row) => row.id === current) ? current : rows[0]?.id ?? "");
    }).catch((error) => {
      if (controller.signal.aborted) return;
      setWorkspaces([]);
      setOrganizationId("");
      if (!(error instanceof ApiError && (error.status === 401 || (error.status === 403 && error.code === "USER_NOT_PROVISIONED")))) {
        setWorkspaceError(errorMessage(error));
      }
    }).finally(() => {
      if (!controller.signal.aborted) {
        setWorkspaceLoading(false);
        setWorkspacesResolved(true);
      }
    });
    return () => controller.abort();
  }, [discoveryIdentity, reloadToken]);

  const workspace = session ? workspaces.find((row) => row.id === organizationId) : undefined;
  const identity = useMemo<FixtureIdentity>(() => ({
    ...discoveryIdentity,
    key: `${discoveryIdentity.key}:${workspace?.id ?? ""}`,
    organizationId: workspace?.id ?? "",
    organizationLabel: workspace?.name ?? "Select a workspace",
  }), [discoveryIdentity, workspace]);

  const value: IdentityContextValue = {
    authMode: "supabase", identity, workspace, workspaces,
    workspaceLoading: Boolean(session) && (!workspacesResolved || workspaceLoading), workspaceError, authError,
    sessionLoading: session === undefined, signedIn: Boolean(session),
    setIdentityKey: (id) => {
      if (workspaces.some((row) => row.id === id)) setOrganizationId(id);
    },
    reloadWorkspace: () => setReloadToken((count) => count + 1),
    signIn, signOut, signInWithGoogle, googleOAuthEnabled: GOOGLE_OAUTH_ENABLED,
  };
  return <IdentityContext.Provider value={value}>{children}</IdentityContext.Provider>;
}
