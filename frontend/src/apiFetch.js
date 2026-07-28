import { supabase } from "./supabaseClient";

// Set VITE_API_BASE_URL in production (Vercel/Netlify env vars) to point
// at the deployed backend; falls back to localhost for local dev.
export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

/**
 * fetch(), but with the current Supabase session's access token attached
 * as an Authorization header automatically -- every backend route now
 * requires this (@require_auth in app.py) except the two public
 * mock-interview company/difficulty-mix endpoints. Every page component
 * should call this instead of raw fetch() for anything hitting API_BASE,
 * so there's exactly one place that knows how to attach the token instead
 * of repeating that logic in every component.
 *
 * If there's no active session (shouldn't normally happen -- the whole
 * app is gated behind a login screen in App.jsx), this just omits the
 * header and lets the backend's own 401 handle it, same as any other
 * auth failure.
 */
export async function apiFetch(path, options = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  return fetch(`${API_BASE}${path}`, { ...options, headers });
}