import { Handle, Position } from "reactflow";

// No fixed denominator (per earlier decision) -- color just reflects
// whether you've made any progress on this topic at all, not "% complete."
// Four tiers instead of three: once a topic is extensively covered (10+
// solved -- e.g. Arrays & Hashing, which everyone racks up fast) it goes
// green instead of just matching the "some progress" cyan, so heavily
// practiced topics visually stand out on the tree instead of blending in
// with topics you've barely started.
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