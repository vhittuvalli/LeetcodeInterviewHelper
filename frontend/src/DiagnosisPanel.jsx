import { useState, useCallback } from "react";
import { apiFetch } from "./apiFetch";

const DIAGNOSIS_LIMIT = 3;

// Sent as X-API-Key on the routes that actually cost money -- a no-op if
// VITE_API_SHARED_SECRET isn't set (local dev), since the backend only
// enforces this check when its own API_SHARED_SECRET is configured too.
const API_SHARED_SECRET = import.meta.env.VITE_API_SHARED_SECRET || "";

const VERDICT_LABELS = {
  OPTIMAL: "Optimal",
  SUBOPTIMAL: "Suboptimal",
  WRONG: "Wrong",
};

export default function DiagnosisPanel() {
  const [status, setStatus] = useState("idle"); // idle | loading | ready | error
  const [results, setResults] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");

  // Deliberately NOT auto-run on mount -- this hits a real LLM API and
  // costs actual money per call, so it only fires when the button below is
  // clicked, same reasoning as why the backend route is a POST not a GET.
  const runDiagnosis = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await apiFetch(`/api/diagnosis/run?limit=${DIAGNOSIS_LIMIT}`, {
        method: "POST",
        headers: API_SHARED_SECRET ? { "X-API-Key": API_SHARED_SECRET } : {},
      });
      const body = await res.json();

      if (!res.ok) {
        setErrorMessage(body.message || "Something went wrong.");
        setStatus("error");
        return;
      }

      setResults(body);
      setStatus("ready");
    } catch (err) {
      console.error(err);
      setErrorMessage("Couldn't reach the backend.");
      setStatus("error");
    }
  }, []);

  return (
    <div>
      <button className="btn btn--primary" onClick={runDiagnosis} disabled={status === "loading"}>
        {status === "loading" ? "Diagnosing..." : "Diagnose weak problems"}
      </button>

      {status === "idle" && (
        <p className="hint-text" style={{ marginTop: 14 }}>
          Picks a few of your weakest-topic solved problems and gets AI feedback on each --
          uses a real API call, costs a small amount.
        </p>
      )}

      {status === "error" && (
        <p className="error-text" style={{ marginTop: 14 }}>
          {errorMessage}
        </p>
      )}

      {status === "ready" && results.length === 0 && (
        <div className="empty-state" style={{ marginTop: 16 }}>
          Nothing left to diagnose right now -- solve some new problems first.
        </div>
      )}

      {status === "ready" && results.length > 0 && (
        <div className="card-grid" style={{ marginTop: 18 }}>
          {results.map((r) => {
            const verdictClass = r.skipped ? "skipped" : (r.verdict || "unknown").toLowerCase();
            return (
              <div className={`diag-card diag-card--${verdictClass}`} key={r.titleSlug}>
                <div className="diag-card__top">
                  {r.skipped ? (
                    <span className="badge badge--skipped">No new submission</span>
                  ) : (
                    <span className={`badge badge--${(r.verdict || "unknown").toLowerCase()}`}>
                      {VERDICT_LABELS[r.verdict] || r.verdict || "Unknown"}
                    </span>
                  )}
                </div>

                <a
                  className="diag-card__title"
                  href={`https://leetcode.com/problems/${r.titleSlug}/`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {r.title}
                </a>

                <p className="diag-card__text">{r.diagnosis}</p>

                <a
                  className="diag-card__cta"
                  href={`https://leetcode.com/problems/${r.titleSlug}/`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View on LeetCode
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M7 17L17 7M9 7h8v8" />
                  </svg>
                </a>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}