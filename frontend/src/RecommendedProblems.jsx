import { useState, useCallback, useEffect } from "react";
import { apiFetch } from "./apiFetch";

const RECOMMENDATION_LIMIT = 6;

export default function RecommendedProblems() {
  const [recommendations, setRecommendations] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | empty | error

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await apiFetch(`/api/recommendations?limit=${RECOMMENDATION_LIMIT}`);
      const body = await res.json();

      if (!res.ok) {
        setStatus("error");
        return;
      }

      if (!body.recommendations || body.recommendations.length === 0) {
        setStatus("empty");
        return;
      }

      setRecommendations(body.recommendations);
      setStatus("ready");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (status === "loading") {
    return <div className="status-screen__spinner" />;
  }

  if (status === "error") {
    return <p className="error-text">Couldn&apos;t load recommendations.</p>;
  }

  if (status === "empty") {
    return (
      <div className="empty-state">
        No recommendations right now -- solve a few more problems so weak topics can surface.
      </div>
    );
  }

  return (
    <div className="card-grid">
      {recommendations.map((rec, i) => {
        const difficulty = rec.problem.difficulty.toLowerCase();
        return (
          <div className={`rec-card rec-card--${difficulty}`} key={rec.problem.titleSlug}>
            {rec.isRetry && <span className="rec-card__ribbon">Finish this one</span>}

            <div className="rec-card__top">
              <span className="rec-card__rank">{i + 1}</span>
              <span className={`difficulty difficulty--${difficulty}`}>{rec.problem.difficulty}</span>
            </div>

            <a
              className="rec-card__title"
              href={`https://leetcode.com/problems/${rec.problem.titleSlug}/`}
              target="_blank"
              rel="noreferrer"
            >
              {rec.problem.frontendId}. {rec.problem.title}
            </a>

            <span className="rec-card__topic-chip">
              <span className="rec-card__topic-dot" />
              {rec.topic}
            </span>

            <p className="rec-card__reason">{rec.reason}</p>

            <a
              className="rec-card__cta"
              href={`https://leetcode.com/problems/${rec.problem.titleSlug}/`}
              target="_blank"
              rel="noreferrer"
            >
              Solve on LeetCode
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M7 17L17 7M9 7h8v8" />
              </svg>
            </a>
          </div>
        );
      })}
    </div>
  );
}