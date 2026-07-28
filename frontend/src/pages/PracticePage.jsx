import SpacedRepetitionCard from "../SpacedRepetitionCard";
import DiagnosisPanel from "../DiagnosisPanel";
import RecommendedProblems from "../RecommendedProblems";

export default function PracticePage() {
  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar__title">Practice</div>
          <div className="topbar__subtitle">Your daily review, AI diagnosis, and next recommendations in one place</div>
        </div>
      </div>

      <div className="page-scroll">
        <section className="page-section">
          <h2 className="page-section__title">Daily Review</h2>
          <p className="page-section__desc">
            One spaced-repetition pick a day, favoring NeetCode 150 first.
          </p>
          <SpacedRepetitionCard />
        </section>

        <section className="page-section">
          <h2 className="page-section__title">AI Diagnosis</h2>
          <p className="page-section__desc">
            LLM feedback on your weakest-topic solves -- wrong answers get a nudge, suboptimal
            ones get pointed at the better approach, optimal ones get style nitpicks.
          </p>
          <DiagnosisPanel />
        </section>

        <section className="page-section">
          <h2 className="page-section__title">Recommendations</h2>
          <p className="page-section__desc">
            Unsolved problems from your weakest topics, ranked first.
          </p>
          <RecommendedProblems />
        </section>
      </div>
    </>
  );
}