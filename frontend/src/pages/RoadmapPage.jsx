import { useCallback, useState } from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import TopicNode from "../TopicNode";

const nodeTypes = { topic: TopicNode };

export default function RoadmapPage({ nodes, edges, onRefresh }) {
  const [selectedTopic, setSelectedTopic] = useState(null);

  const onNodeClick = useCallback((_, node) => {
    setSelectedTopic(node.data);
  }, []);

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar__title">Roadmap</div>
          <div className="topbar__subtitle">Your solved problems, grouped by topic and prerequisite order</div>
        </div>
        <button className="btn btn--ghost" onClick={onRefresh}>
          Refresh
        </button>
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
          <Background color="#1b2333" gap={22} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>

        {selectedTopic && (
          <div className="side-panel">
            <div className="side-panel__header">
              <h3>{selectedTopic.label}</h3>
              <button className="btn btn--ghost" onClick={() => setSelectedTopic(null)}>
                Close
              </button>
            </div>
            {selectedTopic.problems.length === 0 ? (
              <p className="hint-text">No solved problems here yet.</p>
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
                    </a>
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
    </>
  );
}