"""Contract impact graph: contract -> slices -> rework/regate tasks -> gates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContractImpactGraph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, str]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)

    def add_node(self, node_id: str, kind: str, label: str = "") -> None:
        self.nodes[node_id] = {"id": node_id, "kind": kind,
                               "label": label or node_id}

    def add_edge(self, src: str, dst: str, relation: str) -> None:
        self.add_node(src, self.nodes.get(src, {}).get("kind", "unknown"),
                      self.nodes.get(src, {}).get("label", src))
        self.add_node(dst, self.nodes.get(dst, {}).get("kind", "unknown"),
                      self.nodes.get(dst, {}).get("label", dst))
        edge = {"from": src, "to": dst, "relation": relation}
        if edge not in self.edges:
            self.edges.append(edge)

    def record_change(self, *, contract: str, from_version: str, to_version: str,
                      slices: list[str], tasks: list[str],
                      invalidated: int, evidence_ids: list[str] | None = None) -> dict[str, Any]:
        change = {
            "contract": contract,
            "from_version": from_version,
            "to_version": to_version,
            "impacted_slices": slices,
            "impacted_tasks": tasks,
            "invalidated_evidence": invalidated,
            "evidence_ids": evidence_ids or [],
        }
        self.changes.append(change)
        return change

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges),
            "changes": list(self.changes),
        }
