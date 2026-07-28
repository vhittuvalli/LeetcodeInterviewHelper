import { createContext, useContext, useEffect, useState } from "react";
import { supabase } from "./supabaseClient";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(undefined); // undefined = still loading, null = logged out
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    // Grabs whatever session is already stashed (Supabase persists it in
    // memory + localStorage under the hood, and handles refresh-token
    // rotation on its own -- nothing here needs to think about token
    // expiry directly).
    supabase.auth.getSession()
      .then(({ data, error }) => {
        if (error) setAuthError(error.message);
        setSession(data.session);
      })
      .catch((err) => {
        setAuthError(err.message || "Could not reach the authentication service.");
        setSession(null);
      });

    // Keeps session in sync with sign-in/sign-out/token-refresh events
    // fired from anywhere in the app (e.g. LoginPage calling
    // signInWithPassword), so this provider is the single source of
    // truth every other component reads from.
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{ session, user: session?.user ?? null, authError, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth() must be called from inside <AuthProvider>");
  }
  return ctx;
}