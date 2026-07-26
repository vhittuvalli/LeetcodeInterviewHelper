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
    return <div className="daily-review daily-review--muted">Loading today's review...</div>;
  }

  if (status === "empty") {
    return <div className="daily-review daily-review--muted">Solve something on LeetCode to start reviewing.</div>;
  }

  if (status === "error") {
    return <div className="daily-review daily-review--muted">Couldn&apos;t load today&apos;s review.</div>;
  }

  const { problem, isNeetcode150, reviewedCount, totalSolved } = data;

  return (
    <div className="daily-review">
      <span className="daily-review__label">Today&apos;s review:</span>
      <a href={`https://leetcode.com/problems/${problem.titleSlug}/`} target="_blank" rel="noreferrer">
        {problem.frontendId}. {problem.title}
      </a>
      <span className={`difficulty difficulty--${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span>
      {isNeetcode150 && <span className="badge badge--neetcode">NeetCode 150</span>}
      <button onClick={markReviewed}>Mark reviewed</button>
      <span className="daily-review__progress">
        {reviewedCount}/{totalSolved} reviewed
      </span>
    </div>
  );
}