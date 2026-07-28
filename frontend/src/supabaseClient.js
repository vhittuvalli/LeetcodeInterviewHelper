import { createClient } from "@supabase/supabase-js";

// Same project as the backend's DATABASE_URL points at -- this is the
// public anon key (safe to ship in the frontend bundle by design, same
// as VITE_API_SHARED_SECRET), used only for auth (sign up/in/out, session
// refresh). It cannot read or write any of the app's actual data tables --
// RLS denies the anon/authenticated roles by default (enable_rls.sql),
// and everything real still goes through the Flask backend.
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  // Fails loudly at import time rather than letting every auth call fail
  // mysteriously later -- this only ever fires if .env is missing the
  // two Supabase vars, which is worth knowing about immediately.
  console.error(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY -- copy them from " +
    "Supabase's Project Settings -> API into frontend/.env (see .env.example)."
  );
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);