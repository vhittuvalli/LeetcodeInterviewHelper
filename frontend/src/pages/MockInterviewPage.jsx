import { useState, useEffect, useCallback, useMemo, useRef } from "react";

const API_BASE = "http://localhost:5000";

function formatClock(seconds) {
  const clamped = Math.max(0, Math.round(seconds));
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function MockInterviewPage() {
  // step: pick -> ready -> active -> result
  const [step, setStep] = useState("pick");

  const [companies, setCompanies] = useState([]);
  const [companiesStatus, setCompaniesStatus] = useState("loading"); // loading | ready | error
  const [query, setQuery] = useState("");
  const [company, setCompany] = useState(null);

  const [mix, setMix] = useState(null);
  const [mixStatus, setMixStatus] = useState("idle"); // idle | loading | ready | error

  const [round, setRound] = useState(null); // { problem, startedAt, timeLimitSeconds }
  const [startError, setStartError] = useState("");
  const [now, setNow] = useState(() => Date.now() / 1000);

  const [evalStatus, setEvalStatus] = useState("idle"); // idle | loading | error
  const [evalError, setEvalError] = useState("");
  const [result, setResult] = useState(null);

  const tickRef = useRef(null);

  useEffect(() => {
    const load = async () => {
      setCompaniesStatus("loading");
      try {
        const res = await fetch(`${API_BASE}/api/mock-interview/companies`);
        const body = await res.json();
        if (!res.ok) throw new Error(body.message || "Failed to load companies");
        setCompanies(body);
        setCompaniesStatus("ready");
      } catch (err) {
        console.error(err);
        setCompaniesStatus("error");
      }
    };
    load();
  }, []);

  const filteredCompanies = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return companies.filter((c) => c.toLowerCase().includes(q)).slice(0, 8);
  }, [companies, query]);

  const pickCompany = useCallback(async (name) => {
    setCompany(name);
    setQuery("");
    setStep("ready");
    setMixStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/api/mock-interview/difficulty-mix?company=${encodeURIComponent(name)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to load difficulty mix");
      setMix(body);
      setMixStatus("ready");
    } catch (err) {
      console.error(err);
      setMixStatus("error");
    }
  }, []);

  const changeCompany = () => {
    setStep("pick");
    setCompany(null);
    setMix(null);
    setMixStatus("idle");
  };

  const startRound = useCallback(async () => {
    setStartError("");
    try {
      const res = await fetch(`${API_BASE}/api/mock-interview/start?company=${encodeURIComponent(company)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to start round");
      setRound(body);
      setNow(body.startedAt);
      setResult(null);
      setStep("active");
    } catch (err) {
      console.error(err);
      setStartError(err.message || "Couldn't start a round.");
    }
  }, [company]);

  // Countdown -- purely client-side display; the backend independently
  // checks the real submission timestamp against startedAt/timeLimitSeconds
  // when evaluating, so nothing here needs to be trusted for grading.
  useEffect(() => {
    if (step !== "active") return;
    tickRef.current = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(tickRef.current);
  }, [step]);

  const remaining = round ? round.timeLimitSeconds - (now - round.startedAt) : 0;
  const timeUp = remaining <= 0;

  const submitForEvaluation = useCallback(async () => {
    setEvalStatus("loading");
    setEvalError("");
    try {
      const res = await fetch(`${API_BASE}/api/mock-interview/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          problem: round.problem,
          startedAt: round.startedAt,
          timeLimitSeconds: round.timeLimitSeconds,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Evaluation failed");
      setResult(body);
      setEvalStatus("idle");
      setStep("result");
    } catch (err) {
      console.error(err);
      setEvalError(err.message || "Couldn't evaluate this round.");
      setEvalStatus("error");
    }
  }, [round]);

  const startAnother = () => {
    setRound(null);
    setResult(null);
    setStartError("");
    setStep("ready");
  };

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar__title">Company Mock Interview</div>
          <div className="topbar__subtitle">
            One timed round, sampled the way that company's real interviews actually skew
          </div>
        </div>
      </div>

      <div className="page-scroll">
        {step === "pick" && (
          <div className="mock-picker">
            {companiesStatus === "loading" && <div className="status-screen__spinner" />}
            {companiesStatus === "error" && <p className="error-text">Couldn&apos;t load the company list.</p>}

            {companiesStatus === "ready" && (
              <>
                <input
                  className="mock-picker__input"
                  type="text"
                  placeholder="Search for a company (e.g. Amazon, Google, Meta)..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  autoFocus
                />
                {filteredCompanies.length > 0 && (
                  <ul className="mock-picker__list">
                    {filteredCompanies.map((c) => (
                      <li key={c}>
                        <button className="mock-picker__option" onClick={() => pickCompany(c)}>
                          {c}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {query.trim() && filteredCompanies.length === 0 && (
                  <p className="hint-text" style={{ marginTop: 10 }}>
                    No companies match &quot;{query}&quot;.
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {step === "ready" && (
          <div className="mock-setup">
            <div className="mock-setup__company">
              <span className="mock-setup__company-name">{company}</span>
              <button className="btn btn--ghost" onClick={changeCompany}>
                Change
              </button>
            </div>

            {mixStatus === "loading" && <div className="status-screen__spinner" />}
            {mixStatus === "error" && <p className="error-text">Couldn&apos;t load this company&apos;s difficulty mix.</p>}

            {mixStatus === "ready" && mix && (
              <div className="mix-bar">
                <div className="mix-bar__track">
                  {mix.Easy > 0 && <div className="mix-bar__seg mix-bar__seg--easy" style={{ width: `${mix.Easy}%` }} />}
                  {mix.Medium > 0 && (
                    <div className="mix-bar__seg mix-bar__seg--medium" style={{ width: `${mix.Medium}%` }} />
                  )}
                  {mix.Hard > 0 && <div className="mix-bar__seg mix-bar__seg--hard" style={{ width: `${mix.Hard}%` }} />}
                </div>
                <div className="mix-bar__legend">
                  <span>
                    <i className="mix-bar__dot mix-bar__dot--easy" /> Easy {mix.Easy}%
                  </span>
                  <span>
                    <i className="mix-bar__dot mix-bar__dot--medium" /> Medium {mix.Medium}%
                  </span>
                  <span>
                    <i className="mix-bar__dot mix-bar__dot--hard" /> Hard {mix.Hard}%
                  </span>
                </div>
              </div>
            )}

            <p className="hint-text" style={{ marginTop: 14 }}>
              One 45-minute round. The problem's difficulty is sampled from {company}&apos;s real distribution above,
              weighted toward what's actually been reported most often.
            </p>

            {startError && <p className="error-text">{startError}</p>}

            <button className="btn btn--primary" onClick={startRound} style={{ marginTop: 14 }}>
              Start round
            </button>
          </div>
        )}

        {step === "active" && round && (
          <div className={`interview-card interview-card--${round.problem.difficulty.toLowerCase()}`}>
            <div className={`interview-card__timer${timeUp ? " interview-card__timer--up" : ""}`}>
              {timeUp ? "Time's up" : formatClock(remaining)}
            </div>

            <div className="interview-card__top">
              <span className="hint-text">{company}</span>
              <span className={`difficulty difficulty--${round.problem.difficulty.toLowerCase()}`}>
                {round.problem.difficulty}
              </span>
            </div>

            <a
              className="interview-card__title"
              href={`https://leetcode.com/problems/${round.problem.titleSlug}/`}
              target="_blank"
              rel="noreferrer"
            >
              {round.problem.title}
            </a>

            {round.problem.topics && round.problem.topics.length > 0 && (
              <div className="interview-card__topics">
                {round.problem.topics.map((t) => (
                  <span className="badge badge--skipped" key={t}>
                    {t}
                  </span>
                ))}
              </div>
            )}

            <p className="hint-text">
              Solve it on LeetCode, then come back and submit for evaluation. Your most recent submission on this
              problem will be graded.
            </p>

            {evalError && <p className="error-text">{evalError}</p>}

            <div className="interview-card__actions">
              <a
                className="review-card__cta"
                href={`https://leetcode.com/problems/${round.problem.titleSlug}/`}
                target="_blank"
                rel="noreferrer"
              >
                Open on LeetCode
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M7 17L17 7M9 7h8v8" />
                </svg>
              </a>
              <button className="btn btn--primary" onClick={submitForEvaluation} disabled={evalStatus === "loading"}>
                {evalStatus === "loading" ? "Evaluating..." : timeUp ? "Time's up -- submit for evaluation" : "I'm done -- evaluate"}
              </button>
            </div>
          </div>
        )}

        {step === "result" && result && round && (
          <div className={`result-card result-card--${result.outcome}`}>
            <span className="result-card__outcome">{result.outcomeLabel}</span>

            <a
              className="result-card__title"
              href={`https://leetcode.com/problems/${round.problem.titleSlug}/`}
              target="_blank"
              rel="noreferrer"
            >
              {round.problem.title}
            </a>

            <div className="result-card__meta">
              <span className={`difficulty difficulty--${round.problem.difficulty.toLowerCase()}`}>
                {round.problem.difficulty}
              </span>
              {result.verdict && <span className={`badge badge--${result.verdict.toLowerCase()}`}>{result.verdict}</span>}
              {result.timeTakenSeconds != null && (
                <span className="hint-text">Solved in {formatClock(result.timeTakenSeconds)}</span>
              )}
            </div>

            <p className="result-card__feedback">{result.feedback}</p>

            <button className="btn btn--primary" onClick={startAnother}>
              Start another round
            </button>
          </div>
        )}
      </div>
    </>
  );
}