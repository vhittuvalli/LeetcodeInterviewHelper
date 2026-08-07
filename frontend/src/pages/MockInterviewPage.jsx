import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { apiFetch } from "../apiFetch";

const ROUNDS_OPTIONS = [2, 3, 4, 5];

const API_SHARED_SECRET = import.meta.env.VITE_API_SHARED_SECRET || "";

const OUTCOME_LABELS = {
  strong_pass: "Strong Pass",
  pass: "Pass",
  no_pass: "No Pass",
};

function formatClock(seconds) {
  const clamped = Math.max(0, Math.round(seconds));
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const OUTCOME_SCORES = { strong_pass: 100, pass: 60, no_pass: 0 };

function loopScore(results) {
  if (results.length === 0) return 0;
  const total = results.reduce((sum, r) => sum + OUTCOME_SCORES[r.result.outcome], 0);
  return Math.round(total / results.length);
}

function aggregateOutcome(score) {
  if (score >= 85) return "strong_pass";
  if (score >= 50) return "pass";
  return "no_pass";
}

export default function MockInterviewPage() {
  const [step, setStep] = useState("pick");

  const [companies, setCompanies] = useState([]);
  const [companiesStatus, setCompaniesStatus] = useState("loading");
  const [query, setQuery] = useState("");
  const [company, setCompany] = useState(null);

  const [mix, setMix] = useState(null);
  const [mixStatus, setMixStatus] = useState("idle");

  const [mode, setMode] = useState("single");
  const [roundsCount, setRoundsCount] = useState(3);

  const [loopProblems, setLoopProblems] = useState([]);
  const [currentRoundIndex, setCurrentRoundIndex] = useState(0);
  const [roundResults, setRoundResults] = useState([]);

  const [round, setRound] = useState(null);
  const [startError, setStartError] = useState("");
  const [now, setNow] = useState(() => Date.now() / 1000);

  const [evalStatus, setEvalStatus] = useState("idle");
  const [evalError, setEvalError] = useState("");
  const [result, setResult] = useState(null);

  const tickRef = useRef(null);

  useEffect(() => {
    const load = async () => {
      setCompaniesStatus("loading");
      try {
        const res = await apiFetch("/api/mock-interview/companies");
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
    setMode("single");
    setRoundsCount(3);
    setStep("ready");
    setMixStatus("loading");
    try {
      const res = await apiFetch(`/api/mock-interview/difficulty-mix?company=${encodeURIComponent(name)}`);
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

  const beginRound = (problem, timeLimitSeconds) => {
    setRound({ problem, startedAt: Date.now() / 1000, timeLimitSeconds });
    setNow(Date.now() / 1000);
    setResult(null);
    setEvalError("");
    setStep("active");
  };

  const startRound = useCallback(async () => {
    setStartError("");
    try {
      const res = await apiFetch(`/api/mock-interview/start?company=${encodeURIComponent(company)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to start round");
      beginRound(body.problem, body.timeLimitSeconds);
    } catch (err) {
      console.error(err);
      setStartError(err.message || "Couldn't start a round.");
    }
  }, [company]);

  const startLoop = useCallback(async () => {
    setStartError("");
    try {
      const res = await apiFetch(
        `/api/mock-interview/start-loop?company=${encodeURIComponent(company)}&rounds=${roundsCount}`
      );
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Failed to start loop");
      setLoopProblems(body.problems);
      setCurrentRoundIndex(0);
      setRoundResults([]);
      beginRound(body.problems[0], body.timeLimitSeconds);
    } catch (err) {
      console.error(err);
      setStartError(err.message || "Couldn't start a loop.");
    }
  }, [company, roundsCount]);

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
      const res = await apiFetch("/api/mock-interview/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(API_SHARED_SECRET ? { "X-API-Key": API_SHARED_SECRET } : {}),
        },
        body: JSON.stringify({
          problem: round.problem,
          startedAt: round.startedAt,
          timeLimitSeconds: round.timeLimitSeconds,
          company,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.message || "Evaluation failed");
      setResult(body);
      setEvalStatus("idle");
      if (mode === "loop") {
        setRoundResults((prev) => [...prev, { problem: round.problem, result: body }]);
      }
      setStep("result");
    } catch (err) {
      console.error(err);
      setEvalError(err.message || "Couldn't evaluate this round.");
      setEvalStatus("error");
    }
  }, [round, mode, company]);

  const goToNextRound = () => {
    const nextIndex = currentRoundIndex + 1;
    setCurrentRoundIndex(nextIndex);
    beginRound(loopProblems[nextIndex], round.timeLimitSeconds);
  };

  const finishLoop = () => setStep("loop-summary");

  const startAnother = () => {
    setRound(null);
    setResult(null);
    setStartError("");
    setLoopProblems([]);
    setRoundResults([]);
    setCurrentRoundIndex(0);
    setStep("ready");
  };

  const isLastRound = mode === "loop" && currentRoundIndex >= loopProblems.length - 1;
  const overallScore = mode === "loop" ? loopScore(roundResults) : null;
  const overall = mode === "loop" && roundResults.length > 0 ? aggregateOutcome(overallScore) : null;

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar__title">Company Mock Interview</div>
          <div className="topbar__subtitle">
            Timed rounds, sampled the way that company's real interviews actually skew
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

            <div className="mode-toggle">
              <button
                className={`mode-toggle__option${mode === "single" ? " mode-toggle__option--active" : ""}`}
                onClick={() => setMode("single")}
              >
                Single Round
              </button>
              <button
                className={`mode-toggle__option${mode === "loop" ? " mode-toggle__option--active" : ""}`}
                onClick={() => setMode("loop")}
              >
                Full Loop
              </button>
            </div>

            {mode === "single" && (
              <p className="hint-text" style={{ marginTop: 14 }}>
                One 45-minute round. The problem's difficulty is sampled from {company}&apos;s real distribution
                above, weighted toward what's actually been reported most often.
              </p>
            )}

            {mode === "loop" && (
              <>
                <p className="hint-text" style={{ marginTop: 14, marginBottom: 10 }}>
                  A back-to-back set of 45-minute rounds, like a real onsite loop -- each with a fresh problem, no
                  repeats. One bad round usually sinks the whole loop, same as it does in real hiring.
                </p>
                <div className="rounds-stepper">
                  {ROUNDS_OPTIONS.map((n) => (
                    <button
                      key={n}
                      className={`rounds-stepper__option${roundsCount === n ? " rounds-stepper__option--active" : ""}`}
                      onClick={() => setRoundsCount(n)}
                    >
                      {n}
                    </button>
                  ))}
                  <span className="hint-text">rounds</span>
                </div>
              </>
            )}

            {startError && <p className="error-text">{startError}</p>}

            <button className="btn btn--primary" onClick={mode === "single" ? startRound : startLoop} style={{ marginTop: 14 }}>
              {mode === "single" ? "Start round" : `Start loop (${roundsCount} rounds)`}
            </button>
          </div>
        )}

        {step === "active" && round && (
          <div className={`interview-card interview-card--${round.problem.difficulty.toLowerCase()}`}>
            {mode === "loop" && (
              <span className="interview-card__round-label">
                Round {currentRoundIndex + 1} of {loopProblems.length}
              </span>
            )}

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
            {mode === "loop" && (
              <span className="interview-card__round-label">
                Round {currentRoundIndex + 1} of {loopProblems.length}
              </span>
            )}

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

            {mode === "single" && (
              <button className="btn btn--primary" onClick={startAnother}>
                Start another round
              </button>
            )}

            {mode === "loop" && !isLastRound && (
              <button className="btn btn--primary" onClick={goToNextRound}>
                Next round ({currentRoundIndex + 2} of {loopProblems.length})
              </button>
            )}

            {mode === "loop" && isLastRound && (
              <button className="btn btn--primary" onClick={finishLoop}>
                See loop summary
              </button>
            )}
          </div>
        )}

        {step === "loop-summary" && (
          <div className={`result-card result-card--${overall}`}>
            <span className="result-card__outcome">{OUTCOME_LABELS[overall]} -- Overall</span>
            <p className="hint-text" style={{ margin: 0 }}>
              {company} loop &middot; {roundResults.length} round{roundResults.length !== 1 ? "s" : ""} &middot; score{" "}
              {overallScore}/100
            </p>

            <div className="loop-summary__rounds">
              {roundResults.map((r, i) => (
                <div className="loop-summary__round" key={r.problem.titleSlug}>
                  <span className="loop-summary__round-index">{i + 1}</span>
                  <a
                    className="loop-summary__round-title"
                    href={`https://leetcode.com/problems/${r.problem.titleSlug}/`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {r.problem.title}
                  </a>
                  <span className={`difficulty difficulty--${r.problem.difficulty.toLowerCase()}`}>
                    {r.problem.difficulty}
                  </span>
                  <span className={`badge badge--${r.result.outcome === "no_pass" ? "wrong" : r.result.outcome === "strong_pass" ? "optimal" : "suboptimal"}`}>
                    {r.result.outcomeLabel}
                  </span>
                </div>
              ))}
            </div>

            <button className="btn btn--primary" onClick={startAnother}>
              Start another loop
            </button>
          </div>
        )}
      </div>
    </>
  );
}