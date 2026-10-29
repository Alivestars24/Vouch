"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useIdentity } from "@/components/identity-context";
import { FIXTURE_IDENTITIES } from "@/lib/api";
import { humanize } from "@/lib/format";
import { SignIn } from "@/components/sign-in";
import { StatePanel } from "@/components/status";
import { BrandMark } from "@/components/brand-mark";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { identity, setIdentityKey, workspace, workspaceLoading, workspaceError,
    authMode, signedIn, workspaces, signOut, reloadWorkspace } =
    useIdentity();

  if (pathname === "/auth/callback") return children;
  if (authMode === "supabase" && !signedIn) return <SignIn />;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <div className="fixture-banner" role="status">
        <strong>{authMode === "supabase" ? "Fixture providers" : "Fixture mode"}</strong>
        <span>Product jobs remain fixtures · Spark transport verified separately · no legal certification</span>
      </div>

      <aside className="sidebar" aria-label="Primary navigation">
        <Link href="/" className="brand-lockup" aria-label="Vouch workspace home">
          <BrandMark />
          <span>
            <strong>Vouch</strong>
            <small>Creators vouch. Brands grow.</small>
          </span>
        </Link>

        <nav className="nav-list">
          <Link href="/" className={pathname === "/" ? "nav-link active" : "nav-link"}>
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m3 10 9-7 9 7v10H3V10Z" /><path d="M9 20v-7h6v7" /></svg>
            Home
          </Link>
          <Link className="nav-link" href="/#campaigns">
            <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M9 10v10" /></svg>
            Campaigns
          </Link>
        </nav>

        <div className="module-rail" aria-label="Vouch modules">
          <p className="eyebrow">Product modules</p>
          <ol>
            <li className={pathname.startsWith("/find") ? "current" : undefined}><Link href="/find"><span aria-hidden="true">01</span><strong>Find</strong><small>Curated evidence</small></Link></li>
            <li className={pathname === "/" || pathname.startsWith("/campaigns") ? "current" : undefined}><Link href="/#campaigns"><span aria-hidden="true">02</span><strong>Check</strong><small>Fixture workflow</small></Link></li>
            <li className={pathname.startsWith("/try") ? "current" : undefined}><Link href="/try"><span aria-hidden="true">03</span><strong>Try</strong><small>India policy gate</small></Link></li>
              <li className={pathname.startsWith("/track") ? "current" : undefined}><Link href="/track"><span aria-hidden="true">04</span><strong>Track</strong><small>Test outcomes</small></Link></li>
          </ol>
        </div>

        <div className="sidebar-prompt">
          <span className="sidebar-prompt-mark" aria-hidden="true">✦</span>
          <p>Move each creator draft from evidence to an explicit human decision.</p>
          <Link href="/#campaigns">Open campaigns <span aria-hidden="true">→</span></Link>
        </div>

        <div className="sidebar-foot">
          <span className="status-dot" aria-hidden="true" />
          <span><strong>{identity.organizationLabel}</strong>Local fixture workspace</span>
        </div>
      </aside>

      <div className="content-shell">
        <header className="topbar">
          <div className="context-block">
            <span className="eyebrow">Current workspace</span>
            <strong>{workspace?.name ?? identity.organizationLabel}</strong>
            <span className="mono context-id">{identity.organizationId}</span>
          </div>

          <div className="identity-controls">
            <div className="role-summary" aria-live="polite">
              {workspaceLoading ? (
                <span className="badge neutral">Loading roles…</span>
              ) : workspaceError ? (
                <span className="badge danger">Identity unavailable</span>
              ) : workspace?.roles.length ? (
                workspace.roles.map((role) => (
                  <span className="badge neutral" key={role}>
                    {humanize(role)}
                  </span>
                ))
              ) : (
                <span className="badge warning">No granted role</span>
              )}
            </div>
            {authMode === "fixture" ? <label className="identity-select">
              <span>Fixture identity</span>
              <select
                value={identity.key}
                onChange={(event) => setIdentityKey(event.target.value)}
                aria-describedby="identity-help"
              >
                {FIXTURE_IDENTITIES.map((item) => (
                  <option value={item.key} key={item.key}>
                    {item.organizationLabel} · {item.label}
                  </option>
                ))}
              </select>
            </label> : <>
              <label className="identity-select">
                <span>Workspace</span>
                <select value={workspace?.id ?? ""} disabled={workspaceLoading || !workspaces?.length} onChange={(event) => {
                  setIdentityKey(event.target.value);
                  router.push("/");
                }}>
                  {!workspace ? <option value="">No workspace selected</option> : null}
                  {workspaces?.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
                </select>
              </label>
              <div className="session-controls">
                <span className="session-email">{identity.user}</span>
                <button className="button secondary small" onClick={() => void signOut?.()}>Sign out</button>
              </div>
            </>}
            <p id="identity-help" className="sr-only">
              {authMode === "fixture" ? "Switching identity changes development fixture headers." : "Workspace selection is checked against your signed-in membership."} Roles are resolved by the API.
            </p>
          </div>
        </header>

        <main id="main-content" tabIndex={-1} className="main-content">
          {authMode === "supabase" && workspaceLoading && !workspace ? (
            <StatePanel kind="loading" title="Opening workspace"><p>Verifying your active organization membership…</p></StatePanel>
          ) : authMode === "supabase" && !workspace ? (
            <StatePanel kind={workspaceError ? "error" : "empty"} title={workspaceError ? "Workspace unavailable" : "No active workspace membership"} action={<button className="button secondary" onClick={reloadWorkspace}>Check membership again</button>}>
              <p>{workspaceError ?? "You are signed in, but no active organization membership is available. Ask your workspace administrator to grant access, or sign out to use a different account."}</p>
            </StatePanel>
          ) : <div key={identity.key}>{children}</div>}
          <footer className="product-colophon"><strong>vouch</strong><span>Evidence first. Human decisions.</span><span>Local product jobs · fixture providers</span></footer>
        </main>
      </div>
    </div>
  );
}
