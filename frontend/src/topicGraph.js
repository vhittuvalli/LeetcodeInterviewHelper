import dagre from "dagre";

// Topic names here must exactly match TOPIC_PRIORITY in backend/leetcode_service.py --
// that's how solvedCount gets matched up to each node later.
export const TOPIC_LIST = [
  "Arrays & Hashing",
  "Two Pointers",
  "Sliding Window",
  "Stack",
  "Binary Search",
  "Linked List",
  "Trees",
  "Heap / Priority Queue",
  "Backtracking",
  "Tries",
  "Graphs",
  "Advanced Graphs",
  "1-D Dynamic Programming",
  "2-D Dynamic Programming",
  "Greedy",
  "Intervals",
  "Math & Geometry",
  "Bit Manipulation",
];

// Prerequisite pairs: [fromTopic, toTopic]. This is the manually curated
// "roadmap shape" -- not derived from data, just your own ordering decision.
export const TOPIC_EDGES = [
  ["Arrays & Hashing", "Two Pointers"],
  ["Arrays & Hashing", "Stack"],
  ["Arrays & Hashing", "Binary Search"],
  ["Two Pointers", "Sliding Window"],
  ["Binary Search", "Linked List"],
  ["Binary Search", "Trees"],
  ["Trees", "Tries"],
  ["Trees", "Heap / Priority Queue"],
  ["Linked List", "Backtracking"],
  ["Backtracking", "Graphs"],
  ["Heap / Priority Queue", "Graphs"],
  ["Heap / Priority Queue", "1-D Dynamic Programming"],
  ["Tries", "1-D Dynamic Programming"],
  ["Graphs", "Advanced Graphs"],
  ["1-D Dynamic Programming", "2-D Dynamic Programming"],
  ["1-D Dynamic Programming", "Greedy"],
  ["Greedy", "Intervals"],
  ["Greedy", "Math & Geometry"],
  ["Math & Geometry", "Bit Manipulation"],
];

const NODE_WIDTH = 190;
const NODE_HEIGHT = 60;

// Runs dagre's layout algorithm over the static topic/edge shape and hands
// back nodes with computed x/y positions -- this replaces hand-placing
// coordinates like the earlier mockup did.
export function buildLayoutedNodes(topicDataByName) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 90 });

  TOPIC_LIST.forEach((topic) => {
    g.setNode(topic, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });
  TOPIC_EDGES.forEach(([from, to]) => {
    g.setEdge(from, to);
  });

  dagre.layout(g);

  const nodes = TOPIC_LIST.map((topic) => {
    const { x, y } = g.node(topic);
    const topicData = topicDataByName[topic];
    return {
      id: topic,
      type: "topic",
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
      data: {
        label: topic,
        solvedCount: topicData ? topicData.solvedCount : 0,
        problems: topicData ? topicData.problems : [],
      },
    };
  });

  const edges = TOPIC_EDGES.map(([from, to]) => ({
    id: `${from}->${to}`,
    source: from,
    target: to,
  }));

  return { nodes, edges };
}