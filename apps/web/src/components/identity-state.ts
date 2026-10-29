import { createContext, useContext } from "react";

import type { FixtureIdentity, Workspace } from "@/lib/types";

export interface IdentityContextValue {
  identity: FixtureIdentity;
  setIdentityKey: (key: string) => void;
  workspace?: Workspace;
  workspaceLoading: boolean;
  workspaceError?: string;
  reloadWorkspace: () => void;
  authMode: "fixture" | "supabase";
  sessionLoading?: boolean;
  signedIn?: boolean;
  authError?: string;
  workspaces?: Workspace[];
  signIn?: (email: string, password: string) => Promise<void>;
  googleOAuthEnabled?: boolean;
  signInWithGoogle?: () => Promise<void>;
  signOut?: () => Promise<void>;
}

export const IdentityContext = createContext<IdentityContextValue | undefined>(undefined);

export function useIdentity(): IdentityContextValue {
  const context = useContext(IdentityContext);
  if (!context) throw new Error("useIdentity must be used within IdentityProvider");
  return context;
}
