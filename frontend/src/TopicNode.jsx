import { Handle, Position } from "reactflow";

function colorForCount(count) {
  if (count === 0) return "topic-node--empty";
  if (count < 5) return "topic-node--some";
  if (count < 10) return "topic-node--active";
  return "topic-node--extensive";
}

export default function TopicNode({ data }) {
  return (
    <div className={`topic-node ${colorForCount(data.solvedCount)}`}>
      <Handle type="target" position={Position.Top} />
      <div className="topic-node__label">{data.label}</div>
      <div className="topic-node__count">{data.solvedCount} solved</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}