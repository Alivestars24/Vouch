import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "fixture";
export const GOOGLE_OAUTH_ENABLED = AUTH_MODE === "supabase" && process.env.NEXT_PUBLIC_GOOGLE_OAUTH_ENABLED === "true";
export const SESSION_EXPIRED_EVENT = "vouch:session-expired";

let client: SupabaseClient | undefined;

export function getSupabaseClient(): SupabaseClient {
  if (AUTH_MODE !== "supabase") throw new Error("Supabase authentication is not enabled.");
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    throw new Error("Authentication is not configured. Ask your administrator to configure the Supabase URL and publishable key.");
  }
  client ??= createClient(url, key, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, flowType: "pkce" },
  });
  return client;
}

export function notifySessionExpired(accessToken?: string) {
  if (AUTH_MODE === "supabase" && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, { detail: accessToken }));
  }
}
