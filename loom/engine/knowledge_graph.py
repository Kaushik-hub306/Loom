"""KnowledgeGraph — in-memory directed graph linking related observations.

Each edge represents a typed relationship between two observations, enabling
traversal, path-finding, and neighbourhood queries.
"""

from __future__ import annotations

from collections import deque
from typing import Literal

RelationType = Literal["caused", "implies", "related_to", "supersedes", "refines"]


class KnowledgeGraph:
    """In-memory directed graph linking related observations.

    Supports adding/removing edges, neighbourhood traversal, path-finding,
    and dumping for serialization.
    """

    def __init__(self):
        # Forward adjacency: source_id -> list of (target_id, relation_type)
        self._forward: dict[str, list[tuple[str, str]]] = {}
        # Reverse adjacency: target_id -> list of (source_id, relation_type)
        self._reverse: dict[str, list[tuple[str, str]]] = {}

    # ── mutation ───────────────────────────────────────────────────────────

    def add_link(self, source_id: str, target_id: str, relation_type: str) -> None:
        """Add a directed edge from *source_id* to *target_id*.

        *relation_type* must be one of ``"caused"``, ``"implies"``,
        ``"related_to"``, ``"supersedes"``, or ``"refines"``.
        """

        if source_id not in self._forward:
            self._forward[source_id] = []
        if target_id not in self._reverse:
            self._reverse[target_id] = []

        # Avoid exact duplicate edges
        existing = [(t, r) for t, r in self._forward[source_id] if t == target_id and r == relation_type]
        if not existing:
            self._forward[source_id].append((target_id, relation_type))
            self._reverse[target_id].append((source_id, relation_type))

    def remove_link(self, source_id: str, target_id: str) -> None:
        """Remove all directed edges from *source_id* to *target_id*.

        Silently does nothing if no such edge exists.
        """

        if source_id in self._forward:
            self._forward[source_id] = [
                (t, r) for t, r in self._forward[source_id] if t != target_id
            ]
            if not self._forward[source_id]:
                del self._forward[source_id]

        if target_id in self._reverse:
            self._reverse[target_id] = [
                (s, r) for s, r in self._reverse[target_id] if s != source_id
            ]
            if not self._reverse[target_id]:
                del self._reverse[target_id]

    # ── queries ────────────────────────────────────────────────────────────

    def get_related(self, observation_id: str, depth: int = 1) -> list[str]:
        """Return all observation IDs reachable from *observation_id* within *depth* hops.

        Uses BFS so results are returned in order of increasing distance.
        The starting observation itself is **not** included.
        """

        if depth < 1:
            return []

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        queue.append((observation_id, 0))
        visited.add(observation_id)

        related: list[str] = []

        while queue:
            current, dist = queue.popleft()
            if dist >= depth:
                continue

            # Follow forward edges (current -> neighbours)
            for neighbour, _rel in self._forward.get(current, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    related.append(neighbour)
                    if dist + 1 < depth:
                        queue.append((neighbour, dist + 1))

            # Follow reverse edges (neighbours -> current)
            for neighbour, _rel in self._reverse.get(current, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    related.append(neighbour)
                    if dist + 1 < depth:
                        queue.append((neighbour, dist + 1))

        return related

    def get_links(self, observation_id: str) -> list[dict]:
        """Return all edges involving *observation_id*.

        Each entry is a dict with ``source``, ``target``, and ``relation`` keys.
        Includes both outgoing and incoming edges.
        """

        edges: list[dict] = []

        # Outgoing
        for target, rel in self._forward.get(observation_id, []):
            edges.append({"source": observation_id, "target": target, "relation": rel})

        # Incoming
        for source, rel in self._reverse.get(observation_id, []):
            edges.append({"source": source, "target": observation_id, "relation": rel})

        return edges

    def find_path(self, source_id: str, target_id: str) -> list[str] | None:
        """Return a shortest path from *source_id* to *target_id*, or ``None``.

        The returned list includes both endpoints (e.g.
        ``[source_id, ..., target_id]``).  A path of ``[source_id]`` is
        returned when source and target are the same node.
        """

        if source_id == target_id:
            return [source_id]

        # BFS
        queue: deque[str] = deque([source_id])
        parent: dict[str, str] = {source_id: source_id}

        while queue:
            current = queue.popleft()

            for neighbour, _rel in self._forward.get(current, []):
                if neighbour not in parent:
                    parent[neighbour] = current
                    if neighbour == target_id:
                        # Reconstruct path
                        path: list[str] = []
                        node: str = neighbour
                        while node != source_id:
                            path.append(node)
                            node = parent[node]
                        path.append(source_id)
                        path.reverse()
                        return path
                    queue.append(neighbour)

            # Also traverse reverse edges (undirected BFS gives shorter paths
            # in sparse graphs when the relationship semantics are bidirectional)
            for neighbour, _rel in self._reverse.get(current, []):
                if neighbour not in parent:
                    parent[neighbour] = current
                    if neighbour == target_id:
                        path = []
                        node = neighbour
                        while node != source_id:
                            path.append(node)
                            node = parent[node]
                        path.append(source_id)
                        path.reverse()
                        return path
                    queue.append(neighbour)

        return None

    # ── introspection ──────────────────────────────────────────────────────

    @property
    def edge_count(self) -> int:
        """Return the total number of directed edges in the graph."""
        return sum(len(v) for v in self._forward.values())

    @property
    def node_count(self) -> int:
        """Return the number of distinct nodes."""
        nodes: set[str] = set(self._forward.keys()) | set(self._reverse.keys())
        return len(nodes)

    def to_dict(self) -> dict:
        """Export all edges as a plain dict for serialization."""
        edges: list[dict] = []
        seen: set[tuple[str, str, str]] = set()
        for source, targets in self._forward.items():
            for target, rel in targets:
                key = (source, target, rel)
                if key not in seen:
                    seen.add(key)
                    edges.append({"source": source, "target": target, "relation": rel})
        return {"edges": edges}

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeGraph":
        """Build a KnowledgeGraph from a dict produced by ``to_dict()``."""
        graph = cls()
        for edge in d.get("edges", []):
            graph.add_link(
                source_id=edge["source"],
                target_id=edge["target"],
                relation_type=edge["relation"],
            )
        return graph
