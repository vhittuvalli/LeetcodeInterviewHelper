import { useState, useCallback, useEffect } from "react";
import { HashRouter, Routes, Route } from "react-router-dom";
import "reactflow/dist/style.css";
import "./App.css";
import { apiFetch } from "./apiFetch";
import { AuthProvider, useAuth } from "./AuthContext";
import { buildLayoutedNodes } from "./topicGraph";
import Layout from "./Layout";
import RoadmapPage from "./pages/RoadmapPage";
import PracticePage from "./pages/PracticePage";
import MockInterviewPage from "./pages/MockInterviewPage";
import HistoryPage from "./pages/HistoryPage";
import AccountPage from "./pages/AccountPage";
import LoginPage from "./pages/LoginPage";

function RoadmapGate({ status, instructions, nodes, edges, onRefresh }) {
  // Only the roadmap's own content depends on whether LeetCode is
  // connected -- every other page (practice, mock interview, history,
  // account) fetches its own data independently and doesn't need this.
  // Rendered *inside* <Layout>, so the sidebar (and therefore the Account
  // page you'd need to visit to fix a "not connected" state) is always
  // reachable, instead of the whole app being replaced by this screen.
  if (status === "loading") {
    return (
      <div className="status-screen">
        <div className="status-screen__spinner" />
        <p>Loading your progress...</p>
      </div>
    );
  }

  if (status === "not_connected") {
    return (
      <div className="status-screen">
        <div className="status-screen__card">
          <h2>Connect your LeetCode account</h2>
          <ol>
            {instructions.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
          <button className="btn btn--primary" onClick={onRefresh}>
            I&apos;ve connected it -- refresh
          </button>
        </div>
      </div>
    );
  }

  if (status === "session_expired") {
    return (
      <div className="status-screen">
        <div className="status-screen__card">
          <h2>Your LeetCode session expired</h2>
          <p>Visit leetcode.com in your browser to renew it, then refresh.</p>
          <button className="btn btn--primary" onClick={onRefresh}>
            Refresh
          </button>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="status-screen">
        <div className="status-screen__card">
          <h2>Couldn&apos;t reach the backend</h2>
          <p>Make sure the Flask server is running on port 5000.</p>
          <button className="btn btn--primary" onClick={onRefresh}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return <RoadmapPage nodes={nodes} edges={edges} onRefresh={onRefresh} />;
}

function AuthenticatedApp() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | not_connected | session_expired | error
  const [instructions, setInstructions] = useState([]);

  // This same /api/topics call doubles as the roadmap's connection check
  // -- it's the cheapest real request that fails with not_connected /
  // session_expired the same way every other route would. Scoped to the
  // roadmap tab only (see RoadmapGate above); it no longer gates the
  // whole app, so a not-yet-connected account can still reach every other
  // page, including Account, where the fix actually happens.
  const loadTopics = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await apiFetch("/api/topics");
      const body = await res.json();

      if (!res.ok) {
        setStatus(body.error === "not_connected" ? "not_connected" : "session_expired");
        setInstructions(body.instructions || []);
        return;
      }

      const byName = {};
      body.forEach((entry) => {
        byName[entry.topic] = entry;
      });

      const { nodes: layoutedNodes, edges: layoutedEdges } = buildLayoutedNodes(byName);
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);
      setStatus("ready");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route
            index
            element={
              <RoadmapGate
                status={status}
                instructions={instructions}
                nodes={nodes}
                edges={edges}
                onRefresh={loadTopics}
              />
            }
          />
          <Route path="practice" element={<PracticePage />} />
          <Route path="mock-interview" element={<MockInterviewPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="account" element={<AccountPage />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}

function Gate() {
  // Two independent gates, checked in order: are you logged into this
  // app at all (session), and only once that's true, is your LeetCode
  // account actually connected (AuthenticatedApp's own loadTopics check).
  // Keeping them separate means a logged-out visitor sees a login screen
  // immediately, never a flash of "connect your LeetCode account" for an
  // account that isn't even signed in yet.
  const { session, authError } = useAuth();

  if (session === undefined) {
    return (
      <div className="status-screen">
        <div className="status-screen__spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  if (authError) {
    return (
      <div className="status-screen">
        <div className="status-screen__card">
          <h2>Couldn&apos;t reach the authentication service</h2>
          <p>{authError}</p>
        </div>
      </div>
    );
  }

  if (session === null) {
    return <LoginPage />;
  }

  return <AuthenticatedApp />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}