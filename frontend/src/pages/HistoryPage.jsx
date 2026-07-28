import { useState, useEffect, useCallback, useMemo } from "react";
import { apiFetch } from "../apiFetch";

const OUTCOME_LABELS = {
  strong_pass: "Strong Pass",
  pass: "Pass",
  no_pass: "No Pass",
};

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatClock(seconds) {
  if (seconds == null) return null;
  const clamped = Math.max(0, Math.round(seconds));
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Same weighting as the loop summary's aggregate score -- keeps "how am I
// doing overall" consistent whether it's one loop or your whole history.
const OUTCOME_SCORES = { strong_pass: 100, pass: 60, no_pass: 0 };

function buildStats(history) {
  const total = history.length;
  const passCount = history.filter((h) => h.outcome !== "no_pass").length;
  const strongCount = history.filter((h) => h.outcome === "strong_pass").length;
  const avgScore = total
    ? Math.round(history.reduce((sum, h) => sum + OUTCOME_SCORES[h.outcome], 0) / total)
    : 0;

  const byCompany = {};
  for (const h of history) {
    if (!byCompany[h.company]) byCompany[h.company] = { rounds: 0, passCount: 0 };
    byCompany[h.company].rounds += 1;
    if (h.outcome !== "no_pass") byCompany[h.company].passCount += 1;
  }
  const companyBreakdown = Object.entries(byCompany)
    .map(([company, stats]) => ({
      company,
      rounds: stats.rounds,
      passRate: Math.round((stats.passCount / stats.rounds) * 100),
    }))
    .sort((a, b) => b.rounds - a.rounds);

  return {
    total,
    passRate: total ? Math.round((passCount / total) * 100) : 0,
    strongRate: total ? Math.round((strongCount / total) * 100) : 0,
    avgScore,
    companyBreakdown,
  };
}

export default function HistoryPage() {
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | empty | error

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await apiFetch("/api/mock-interview/history?limit=100");
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to load history");
      if (body.length === 0) {
        setStatus("empty");
        return;
      }
      setHistory(body);
      setStatus("ready");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => buildStats(history), [history]);

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar__title">Mock Interview History</div>
          <div className="topbar__subtitle">Every graded round, and how you're trending over time</div>
        </div>
        <button className="btn btn--ghost" onClick={load}>
          Refresh
        </button>
      </div>

      <div className="page-scroll">
        {status === "loading" && <div className="status-screen__spinner" />}
        {status === "error" && <p className="error-text">Couldn&apos;t load your mock interview history.</p>}
        {status === "empty" && (
          <div className="empty-state">
            No rounds evaluated yet -- head to Mock Interview and run one to start building history.
          </div>
        )}

        {status === "ready" && (
          <>
            <div className="stats-row">
              <div className="stat-card">
                <span className="stat-card__value">{stats.total}</span>
                <span className="stat-card__label">Rounds evaluated</span>
              </div>
              <div className="stat-card">
                <span className="stat-card__value">{stats.passRate}%</span>
                <span className="stat-card__label">Pass rate</span>
              </div>
              <div className="stat-card">
                <span className="stat-card__value">{stats.strongRate}%</span>
                <span className="stat-card__label">Strong pass rate</span>
              </div>
              <div className="stat-card">
                <span className="stat-card__value">{stats.avgScore}</span>
                <span className="stat-card__label">Avg. score / 100</span>
              </div>
            </div>

            {stats.companyBreakdown.length > 0 && (
              <section className="page-section">
                <h2 className="page-section__title">By Company</h2>
                <div className="company-breakdown">
                  {stats.companyBreakdown.map((c) => (
                    <div className="company-breakdown__row" key={c.company}>
                      <span className="company-breakdown__name">{c.company}</span>
                      <div className="company-breakdown__bar-track">
                        <div className="company-breakdown__bar-fill" style={{ width: `${c.passRate}%` }} />
                      </div>
                      <span className="company-breakdown__pct">{c.passRate}%</span>
                      <span className="hint-text">
                        {c.rounds} round{c.rounds !== 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="page-section">
              <h2 className="page-section__title">All Rounds</h2>
              <div className="history-list">
                {history.map((h, i) => (
                  <div className={`history-row history-row--${h.outcome}`} key={`${h.titleSlug}-${h.createdAt}-${i}`}>
                    <a
                      className="history-row__title"
                      href={`https://leetcode.com/problems/${h.titleSlug}/`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {h.title}
                    </a>
                    <span className="history-row__company">{h.company}</span>
                    <span className={`difficulty difficulty--${h.difficulty.toLowerCase()}`}>{h.difficulty}</span>
                    <span className={`badge badge--${h.outcome === "no_pass" ? "wrong" : h.outcome === "strong_pass" ? "optimal" : "suboptimal"}`}>
                      {OUTCOME_LABELS[h.outcome]}
                    </span>
                    {formatClock(h.timeTakenSeconds) && (
                      <span className="hint-text">{formatClock(h.timeTakenSeconds)}</span>
                    )}
                    <span className="history-row__date">{formatDate(h.createdAt)}</span>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}