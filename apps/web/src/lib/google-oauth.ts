import { AUTH_MODE, getSupabaseClient, GOOGLE_OAUTH_ENABLED } from "@/lib/supabase";

export const GOOGLE_CALLBACK_PATH = "/auth/callback";
export const GOOGLE_SIGN_IN_ERROR = "Google sign-in could not be started. Try again, or use email and password.";
export const GOOGLE_CALLBACK_ERROR = "We could not complete Google sign-in. Return to sign in and try again.";

export async function startGoogleSignIn(): Promise<void> {
  if (AUTH_MODE !== "supabase" || !GOOGLE_OAUTH_ENABLED) throw new Error("Google sign-in is not enabled yet. Use email and password.");
  try {
    const { error } = await getSupabaseClient().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: new URL(GOOGLE_CALLBACK_PATH, window.location.origin).href },
    });
    if (error) throw error;
  } catch {
    throw new Error(GOOGLE_SIGN_IN_ERROR);
  }
}

export async function completeGoogleSignIn(): Promise<void> {
  // Capture only the PKCE inputs, then remove callback data before any exchange or navigation.
  const url = new URL(window.location.href);
  const code = url.searchParams.get("code");
  const flowId = url.searchParams.get("sb_flow_id");
  window.history.replaceState(window.history.state, "", GOOGLE_CALLBACK_PATH);
  try {
    if (
      AUTH_MODE !== "supabase" || !GOOGLE_OAUTH_ENABLED || url.pathname !== GOOGLE_CALLBACK_PATH
      || url.hash || url.searchParams.has("error") || url.searchParams.has("error_code")
      || url.searchParams.has("error_description") || url.searchParams.getAll("code").length !== 1
      || !code || code.length > 4096 || url.searchParams.getAll("sb_flow_id").length > 1
      || (flowId !== null && (!flowId || flowId.length > 256))
    ) throw new Error();
    const { data, error } = await getSupabaseClient().auth.exchangeCodeForSession(
      code, flowId ? { flowId } : undefined,
    );
    if (error || !data.session) throw new Error();
  } catch {
    throw new Error(GOOGLE_CALLBACK_ERROR);
  }
}
