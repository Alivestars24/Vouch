"use client";

import { useState, type FormEvent } from "react";

import { useIdentity } from "@/components/identity-context";
import { StatePanel } from "@/components/status";
import { BrandMark } from "@/components/brand-mark";
import { SignalSculpture } from "@/components/signal-sculpture";

export function SignIn() {
  const { signIn, signInWithGoogle, googleOAuthEnabled, authError, sessionLoading } = useIdentity();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<"password" | "google">();
  const [error, setError] = useState<string>();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!signIn) return;
    setBusy("password");
    setError(undefined);
    try {
      await signIn(email.trim(), password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed. Please try again.");
    } finally {
      setPassword("");
      setBusy(undefined);
    }
  }

  async function continueWithGoogle() {
    if (!googleOAuthEnabled || !signInWithGoogle || busy) return;
    setBusy("google");
    setError(undefined);
    setPassword("");
    try {
      await signInWithGoogle();
    } catch {
      setError("Google sign-in could not be started. Try again, or use email and password.");
      setBusy(undefined);
    }
  }

  return (
    <div className="auth-screen">
      <a className="skip-link" href="#main-content">Skip to sign in</a>
      <div className="fixture-banner" role="status">
        <strong>Fixture providers</strong><span>Supabase sign-in · no live Meta calls or legal certification</span>
      </div>
      <main id="main-content" className="auth-layout" tabIndex={-1}>
        <section className="auth-introduction" aria-labelledby="auth-title">
          <div className="auth-brand"><BrandMark /><strong>Vouch</strong></div>
          <h1 id="auth-title">Creator work.<br />Clear decisions.</h1>
          <p className="lede">Bring each authorized draft, inspect the evidence and make a human call your team can trace.</p>
          <p className="auth-note">Your organization controls membership and review authority. Signing in does not grant access to another workspace.</p>
        </section>
        <section className="auth-panel" aria-labelledby="sign-in-heading">
          <h2 id="sign-in-heading">Sign in to Vouch</h2>
          <p className="auth-panel-lede">Pick up where your team left off.</p>
          {sessionLoading ? (
            <StatePanel kind="loading" title="Checking your session"><p>Restoring your signed-in session…</p></StatePanel>
          ) : (
            <form onSubmit={submit} className="auth-form">
              <div className="field">
                <label htmlFor="sign-in-email">Email</label>
                <input id="sign-in-email" name="email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} disabled={Boolean(busy)} />
              </div>
              <div className="field">
                <label htmlFor="sign-in-password">Password</label>
                <input id="sign-in-password" name="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} disabled={Boolean(busy)} aria-invalid={error || authError ? true : undefined} aria-describedby={error || authError ? "sign-in-error" : undefined} />
              </div>
              {error || authError ? <p id="sign-in-error" className="field-error" role="alert">{error ?? authError}</p> : null}
              <button className="button primary" type="submit" disabled={Boolean(busy)}>{busy === "password" ? "Signing in…" : "Sign in"}</button>
              <button className="button secondary" type="button" onClick={() => void continueWithGoogle()} disabled={!googleOAuthEnabled || !signInWithGoogle || Boolean(busy)} aria-describedby="google-sign-in-help">
                {busy === "google" ? "Opening Google…" : "Continue with Google"}
              </button>
              <p id="google-sign-in-help" className="auth-note">{googleOAuthEnabled ? "Google confirms your identity. Your organization still controls workspace access." : "Google sign-in is not configured yet. Use email and password."}</p>
              <p className="auth-note">Use an account provisioned by your workspace administrator. Self-service registration and password recovery are not enabled in this slice.</p>
            </form>
          )}
        </section>
        <div className="auth-art">
          <SignalSculpture />
          <div className="auth-art-caption"><span>Different perspectives. One clear version.</span><span>Interactive brand study · not an analysis</span></div>
        </div>
      </main>
    </div>
  );
}
