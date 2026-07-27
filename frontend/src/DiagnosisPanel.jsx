import { useState, useCallback } from "react";

const API_BASE = "http://localhost:5000";
const DIAGNOSIS_LIMIT = 3;

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
      const res = await fetch(`${API_BASE}/api/diagnosis/run?limit=${DIAGNOSIS_LIMIT}`, {
        method: "POST",
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
    <div className="diagnosis-panel">
      <div className="diagnosis-panel__header">
        <span className="diagnosis-panel__title">AI diagnosis</span>
        <button onClick={runDiagnosis} disabled={status === "loading"}>
          {status === "loading" ? "Diagnosing..." : "Diagnose weak problems"}
        </button>
      </div>

      {status === "idle" && (
        <p className="diagnosis-panel__hint">
          Picks a few of your weakest-topic solved problems and gets AI feedback on each --
          uses a real API call, costs a small amount.
        </p>
      )}

      {status === "error" && <p className="diagnosis-panel__error">{errorMessage}</p>}

      {status === "ready" && results.length === 0 && (
        <p className="diagnosis-panel__hint">
          Nothing left to diagnose right now -- solve some new problems first.
        </p>
      )}

      {status === "ready" && results.length > 0 && (
        <div className="diagnosis-panel__cards">
          {results.map((r) => (
            <div className="diagnosis-card" key={r.titleSlug}>
              <div className="diagnosis-card__header">
                <a href={`https://leetcode.com/problems/${r.titleSlug}/`} target="_blank" rel="noreferrer">
                  {r.title}
                </a>
                {r.skipped ? (
                  <span className="badge badge--skipped">No new submission</span>
                ) : (
                  <span className={`badge badge--${(r.verdict || "unknown").toLowerCase()}`}>
                    {VERDICT_LABELS[r.verdict] || r.verdict || "Unknown"}
                  </span>
                )}
              </div>
              <p className="diagnosis-card__text">{r.diagnosis}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}