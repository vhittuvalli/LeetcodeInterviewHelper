import { useState, useCallback, useEffect } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";
import "./App.css";
import { buildLayoutedNodes } from "./topicGraph";
import TopicNode from "./TopicNode";

const API_BASE = "http://localhost:5000";
const nodeTypes = { topic: TopicNode };

export default function App() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [status, setStatus] = useState("loading"); // loading | ready | not_connected | session_expired | error
  const [instructions, setInstructions] = useState([]);

  const loadTopics = useCallback(async () => {
    setStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/api/topics`);
      const body = await res.json();

      if (!res.ok) {
        setStatus(body.error === "not_connected" ? "not_connected" : "session_expired");
        setInstructions(body.instructions || []);
        return;
      }

      // body is an array of {topic, solvedCount, problems} -- turn it into
      // a name-keyed lookup so buildLayoutedNodes can merge it into the
      // static graph shape by topic name.
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

  const onNodeClick = useCallback((_, node) => {
    setSelectedTopic(node.data);
  }, []);

  if (status === "loading") {
    return <div className="status-screen">Loading your progress...</div>;
  }

  if (status === "not_connected") {
    return (
      <div className="status-screen">
        <h2>Connect your LeetCode account</h2>
        <ol>
          {instructions.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
        <button onClick={loadTopics}>I&apos;ve connected it -- refresh</button>
      </div>
    );
  }

  if (status === "session_expired") {
    return (
      <div className="status-screen">
        <h2>Your LeetCode session expired</h2>
        <p>Visit leetcode.com in your browser to renew it, then refresh.</p>
        <button onClick={loadTopics}>Refresh</button>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="status-screen">
        <h2>Couldn&apos;t reach the backend</h2>
        <p>Make sure the Flask server is running on port 5000.</p>
        <button onClick={loadTopics}>Retry</button>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="toolbar">
        <button onClick={loadTopics}>Refresh</button>
      </div>

      <div className="tree-container">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          nodesDraggable={false}
          nodesConnectable={false}
          fitView
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {selectedTopic && (
        <div className="side-panel">
          <div className="side-panel__header">
            <h3>{selectedTopic.label}</h3>
            <button onClick={() => setSelectedTopic(null)}>Close</button>
          </div>
          {selectedTopic.problems.length === 0 ? (
            <p>No solved problems here yet.</p>
          ) : (
            <ul>
              {selectedTopic.problems.map((p) => (
                <li key={p.titleSlug}>
                  <a
                    href={`https://leetcode.com/problems/${p.titleSlug}/`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {p.frontendId}. {p.title}
                  </a>{" "}
                  <span className={`difficulty difficulty--${p.difficulty.toLowerCase()}`}>
                    {p.difficulty}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}