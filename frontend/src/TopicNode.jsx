import { Handle, Position } from "reactflow";

// No fixed denominator (per earlier decision) -- color just reflects
// whether you've made any progress on this topic at all, not "% complete."
function colorForCount(count) {
  if (count === 0) return "topic-node--empty";
  if (count < 5) return "topic-node--some";
  return "topic-node--active";
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