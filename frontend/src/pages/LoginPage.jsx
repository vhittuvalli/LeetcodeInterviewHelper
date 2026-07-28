import { useState } from "react";
import { supabase } from "../supabaseClient";

const icons = {
  mail: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="M3.5 6.5l8.5 6.5 8.5-6.5" />
    </svg>
  ),
  lock: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="4.5" y="10.5" width="15" height="10" rx="2.2" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.5l2.3 2.3L15.5 10" />
    </svg>
  ),
};

export default function LoginPage() {
  const [mode, setMode] = useState("signIn"); // signIn | signUp
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | error | check-email
  const [errorMessage, setErrorMessage] = useState("");

  const switchMode = (next) => {
    setMode(next);
    setStatus("idle");
    setErrorMessage("");
  };

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
      <div className="auth-card">
        <div className="auth-card__brand">
          <div className="sidebar__brand-mark auth-card__mark">{"</>"}</div>
          <div>
            <div className="auth-card__brand-text">Interview Prep</div>
            <span className="auth-card__brand-sub">LeetCode co-pilot</span>
          </div>
        </div>

        {status === "check-email" ? (
          <div className="auth-card__success">
            <div className="auth-card__success-icon">{icons.check}</div>
            <h2>Check your inbox</h2>
            <p>
              We sent a confirmation link to <strong>{email}</strong>. Click it, then come back
              and log in.
            </p>
            <button className="btn btn--ghost" style={{ width: "100%" }} onClick={() => switchMode("signIn")}>
              Back to log in
            </button>
          </div>
        ) : (
          <>
            <div className="mode-toggle auth-card__toggle">
              <button
                type="button"
                className={`mode-toggle__option${mode === "signIn" ? " mode-toggle__option--active" : ""}`}
                onClick={() => switchMode("signIn")}
              >
                Log in
              </button>
              <button
                type="button"
                className={`mode-toggle__option${mode === "signUp" ? " mode-toggle__option--active" : ""}`}
                onClick={() => switchMode("signUp")}
              >
                Sign up
              </button>
            </div>

            <p className="auth-card__tagline">
              {mode === "signIn" ? "Welcome back -- log in to continue." : "Create an account to get started."}
            </p>

            <form onSubmit={handleSubmit} className="auth-form">
              <label className="auth-form__label">
                Email
                <div className="auth-form__input-wrap">
                  <span className="auth-form__icon">{icons.mail}</span>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    placeholder="you@example.com"
                  />
                </div>
              </label>

              <label className="auth-form__label">
                Password
                <div className="auth-form__input-wrap">
                  <span className="auth-form__icon">{icons.lock}</span>
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === "signIn" ? "current-password" : "new-password"}
                    placeholder="••••••••"
                  />
                </div>
              </label>

              {status === "error" && <p className="error-text">{errorMessage}</p>}

              <button className="btn btn--primary auth-form__submit" type="submit" disabled={status === "loading"}>
                {status === "loading" ? "Please wait..." : mode === "signIn" ? "Log in" : "Create account"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}