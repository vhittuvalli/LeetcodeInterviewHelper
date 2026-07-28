import { useState, useCallback, useEffect } from "react";

const API_BASE = "http://localhost:5000";

export default function SpacedRepetitionCard() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | empty | error

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/api/spaced-repetition/today`);
      const body = await res.json();

      if (!res.ok) {
        setStatus(body.error === "no_solved_problems" ? "empty" : "error");
        return;
      }

      setData(body);
      setStatus("ready");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markReviewed = async () => {
    if (!data) return;
    await fetch(`${API_BASE}/api/spaced-repetition/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titleSlug: data.problem.titleSlug }),
    });
    load(); // pull the next one immediately, per the backend clearing "current"
  };

  if (status === "loading") {
    return <div className="status-screen__spinner" />;
  }

  if (status === "empty") {
    return <div className="empty-state">Solve something on LeetCode to start reviewing.</div>;
  }

  if (status === "error") {
    return <p className="error-text">Couldn&apos;t load today&apos;s review.</p>;
  }

  const { problem, isNeetcode150, reviewedCount, totalSolved } = data;
  const difficulty = problem.difficulty.toLowerCase();
  const progressPct = totalSolved > 0 ? Math.min(100, Math.round((reviewedCount / totalSolved) * 100)) : 0;

  return (
    <div className={`review-card review-card--${difficulty}`}>
      <div className="review-card__top">
        <span className="review-card__eyebrow">Today&apos;s pick</span>
        <div className="review-card__badges">
          <span className={`difficulty difficulty--${difficulty}`}>{problem.difficulty}</span>
          {isNeetcode150 && <span className="badge badge--neetcode">NeetCode 150</span>}
        </div>
      </div>

      <a
        className="review-card__title"
        href={`https://leetcode.com/problems/${problem.titleSlug}/`}
        target="_blank"
        rel="noreferrer"
      >
        {problem.frontendId}. {problem.title}
      </a>

      <div className="review-card__progress">
        <div className="review-card__progress-track">
          <div className="review-card__progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <span className="review-card__progress-label">
          {reviewedCount}/{totalSolved} reviewed
        </span>
      </div>

      <div className="review-card__actions">
        <button className="btn btn--primary" onClick={markReviewed}>
          Mark reviewed
        </button>
        <a
          className="review-card__cta"
          href={`https://leetcode.com/problems/${problem.titleSlug}/`}
          target="_blank"
          rel="noreferrer"
        >
          Open on LeetCode
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M7 17L17 7M9 7h8v8" />
          </svg>
        </a>
      </div>
    </div>
  );
}