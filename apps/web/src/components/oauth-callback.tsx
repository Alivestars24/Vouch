"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useIdentity } from "@/components/identity-context";
import { StatePanel } from "@/components/status";
import { completeGoogleSignIn, GOOGLE_CALLBACK_ERROR } from "@/lib/google-oauth";

export function OAuthCallback() {
  const router = useRouter();
  const { signOut } = useIdentity();
  const request = useRef<Promise<void> | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    // Strict Mode may replay effects; a single-use PKCE code must be exchanged only once.
    request.current ??= completeGoogleSignIn();
    void request.current.then(() => {
      if (active) router.replace("/");
    }).catch(() => {
      if (!active) return;
      setFailed(true);
      void signOut?.().catch(() => undefined);
    });
    return () => { active = false; };
  }, [router, signOut]);

  return (
    <main id="main-content" tabIndex={-1} className="main-content">
      <div className="page-stack">
        <h1>{failed ? "Sign-in was not completed" : "Completing sign-in"}</h1>
        <StatePanel kind={failed ? "error" : "loading"} title={failed ? "Try signing in again" : "Checking your session"}>
          <p>{failed ? GOOGLE_CALLBACK_ERROR : "Finishing the secure sign-in exchange. Workspace access is verified separately."}</p>
          {failed ? <Link className="button secondary" href="/">Return to sign in</Link> : null}
        </StatePanel>
      </div>
    </main>
  );
}
