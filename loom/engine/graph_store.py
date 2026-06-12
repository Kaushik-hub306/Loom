"""GraphStore — JSON serialization of graph edges to a specified file path.

Reads and writes the knowledge graph in a simple JSON format::

    {"edges": [{"source": "...", "target": "...", "relation": "..."}]}

Missing or unreadable files are handled gracefully by returning an empty graph.
"""

from __future__ import annotations

import json
from pathlib import Path

from .knowledge_graph import KnowledgeGraph


class GraphStore:
    """Persistent storage for KnowledgeGraph edges.

    Parameters
    ----------
    path:
        Path to the ``graph.json`` file on disk.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    # ── persistence ────────────────────────────────────────────────────────

    def load(self) -> KnowledgeGraph:
        """Read graph from disk and return a populated ``KnowledgeGraph``.

        Returns an empty ``KnowledgeGraph`` when the file does not exist or
        cannot be parsed.
        """

        if not self.path.exists():
            return KnowledgeGraph()

        try:
            data = json.loads(self.path.read_text())
            return KnowledgeGraph.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return KnowledgeGraph()

    def save(self, graph: KnowledgeGraph) -> None:
        """Write *graph* edges to disk as JSON."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = graph.to_dict()
        self.path.write_text(json.dumps(data, indent=2))
