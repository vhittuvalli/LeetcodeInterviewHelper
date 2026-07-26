import { useState, useCallback, useEffect } from "react";

const API_BASE = "http://localhost:5000";

export default function RecommendedProblems() {
  const [recommendations, setRecommendations] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | empty | error

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/api/recommendations?limit=2`);
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

  // Supplementary panel, not core to the app -- stay quiet on loading/error/empty
  // instead of taking up space with a message.
  if (status !== "ready") {
    return null;
  }

  return (
    <div className="recommendations-bar">
      <span className="recommendations-bar__title">Recommended problems to do</span>
      <div className="recommendations-bar__cards">
        {recommendations.map((rec) => (
          <div className="recommendation-card" key={rec.problem.titleSlug}>
            <div className="recommendation-card__header">
              <a href={`https://leetcode.com/problems/${rec.problem.titleSlug}/`} target="_blank" rel="noreferrer">
                {rec.problem.frontendId}. {rec.problem.title}
              </a>
              <span className={`difficulty difficulty--${rec.problem.difficulty.toLowerCase()}`}>
                {rec.problem.difficulty}
              </span>
            </div>
            <div className="recommendation-card__meta">
              <span className="recommendation-card__topic">{rec.topic}</span>
              {rec.isRetry && <span className="badge badge--retry">Finish this one</span>}
            </div>
            <div className="recommendation-card__reason">{rec.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}