import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../apiFetch";
import { useAuth } from "../AuthContext";

export default function AccountPage() {
  const { user, signOut } = useAuth();
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [active, setActive] = useState(false);
  const [freshToken, setFreshToken] = useState(""); // only ever held in memory, once
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await apiFetch("/api/account/sync-token");
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to load sync token status");
      setActive(body.active);
      setStatus("ready");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setBusy(true);
    setCopied(false);
    try {
      const res = await apiFetch("/api/account/sync-token", { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to generate token");
      setFreshToken(body.token);
      setActive(true);
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    try {
      await apiFetch("/api/account/sync-token", { method: "DELETE" });
      setActive(false);
      setFreshToken("");
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  const copyToken = async () => {
    try {
      await navigator.clipboard.writeText(freshToken);
      setCopied(true);
    } catch {
      // Clipboard API can fail in some browser/permission contexts -- the
      // token is still selectable text on screen either way, so this
      // isn't a dead end, just a slightly worse click-to-copy experience.
    }
  };

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar__title">Account</div>
          <div className="topbar__subtitle">{user?.email}</div>
        </div>
        <button className="btn btn--ghost" onClick={signOut}>
          Sign out
        </button>
      </div>

      <div className="page-scroll">
        <section className="page-section">
          <h2 className="page-section__title">Chrome Extension Sync Token</h2>
          <p className="page-section__desc">
            The extension can&apos;t see that you&apos;re logged into this site -- browser
            extensions don&apos;t share a web app&apos;s login session. Generate a token here
            and paste it into the extension&apos;s popup once, so it knows which account to
            sync your LeetCode session to.
          </p>

          {status === "loading" && <div className="status-screen__spinner" />}
          {status === "error" && <p className="error-text">Couldn&apos;t load sync token status.</p>}

          {status === "ready" && (
            <div className="card-grid" style={{ marginTop: 16 }}>
              <div className="interview-card">
                <div className="diag-card__top">
                  <span className={`badge badge--${active ? "optimal" : "skipped"}`}>
                    {active ? "Active" : "Not set up"}
                  </span>
                </div>

                {freshToken && (
                  <>
                    <p className="hint-text" style={{ marginTop: 10 }}>
                      Copy this now -- it won&apos;t be shown again. Paste it into the
                      extension&apos;s settings popup.
                    </p>
                    <div className="account-token-box">
                      <code>{freshToken}</code>
                    </div>
                    <button className="btn btn--ghost" onClick={copyToken} style={{ marginTop: 8 }}>
                      {copied ? "Copied!" : "Copy token"}
                    </button>
                  </>
                )}

                <div style={{ marginTop: 16, display: "flex", gap: 10 }}>
                  <button className="btn btn--primary" onClick={generate} disabled={busy}>
                    {active ? "Regenerate token" : "Generate token"}
                  </button>
                  {active && (
                    <button className="btn btn--ghost" onClick={revoke} disabled={busy}>
                      Revoke
                    </button>
                  )}
                </div>

                {active && !freshToken && (
                  <p className="hint-text" style={{ marginTop: 12 }}>
                    A token is active, but it&apos;s only ever shown once at generation time --
                    regenerate if you need to set up the extension on a new device (this
                    invalidates the old one).
                  </p>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}