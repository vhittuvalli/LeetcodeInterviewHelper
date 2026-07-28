import { useState } from "react";
import { supabase } from "../supabaseClient";

export default function LoginPage() {
  const [mode, setMode] = useState("signIn"); // signIn | signUp
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | error | check-email
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("loading");
    setErrorMessage("");

    if (mode === "signIn") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
        setErrorMessage(error.message);
        setStatus("error");
        return;
      }
      // On success, AuthContext's onAuthStateChange listener picks up the
      // new session automatically -- App.jsx re-renders past this screen
      // on its own, nothing to do here.
    } else {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) {
        setErrorMessage(error.message);
        setStatus("error");
        return;
      }
      // Whether this requires email confirmation depends on your
      // Supabase project's Auth settings -- if it does, there's no
      // session yet at this point, so show a clear next step instead of
      // silently doing nothing.
      setStatus("check-email");
    }
  };

  return (
    <div className="status-screen">
      <div className="status-screen__card auth-card">
        <div className="sidebar__brand-mark auth-card__mark">{"</>"}</div>
        <h2>{mode === "signIn" ? "Log in" : "Create your account"}</h2>

        {status === "check-email" ? (
          <p>
            Check <strong>{email}</strong> for a confirmation link, then come back and log in.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <label className="auth-form__label">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </label>

            <label className="auth-form__label">
              Password
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "signIn" ? "current-password" : "new-password"}
              />
            </label>

            {status === "error" && <p className="error-text">{errorMessage}</p>}

            <button className="btn btn--primary" type="submit" disabled={status === "loading"}>
              {status === "loading" ? "Please wait..." : mode === "signIn" ? "Log in" : "Sign up"}
            </button>
          </form>
        )}

        {status !== "check-email" && (
          <button
            type="button"
            className="btn btn--ghost auth-card__switch"
            onClick={() => {
              setMode(mode === "signIn" ? "signUp" : "signIn");
              setStatus("idle");
              setErrorMessage("");
            }}
          >
            {mode === "signIn" ? "Need an account? Sign up" : "Already have an account? Log in"}
          </button>
        )}
      </div>
    </div>
  );
}