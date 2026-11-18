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


RELATIONS = {
    "source_supports_requirement", "scenario_satisfies_requirement",
    "design_realizes_scenario", "code_implements_contract",
    "test_checks_acceptance", "artifact_depends_on", "depends_on",
    "impacts", "rework", "verify", "regate",
}


class TypedImpactGraph:
    """Typed entity graph used to mark current evidence stale on change.

    Relationships are explicit and carry confidence. An unknown or incomplete
    graph is reported, not silently treated as no impact.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    def add_node(self, node_id: str, kind: str, *, label: str = "",
                 version: str = "", confidence: str = "confirmed") -> None:
        self.nodes[node_id] = {"id": node_id, "kind": kind,
                               "label": label or node_id, "version": version,
                               "confidence": confidence}

    def add_edge(self, src: str, dst: str, relation: str, *,
                 confidence: str = "confirmed", source: str = "manual") -> None:
        if relation not in RELATIONS:
            raise ValueError(f"未知影响关系：{relation}")
        self.add_node(src, self.nodes.get(src, {}).get("kind", "unknown"),
                      label=self.nodes.get(src, {}).get("label", src))
        self.add_node(dst, self.nodes.get(dst, {}).get("kind", "unknown"),
                      label=self.nodes.get(dst, {}).get("label", dst))
        edge = {"from": src, "to": dst, "relation": relation,
                "confidence": confidence, "source": source}
        if edge not in self.edges:
            self.edges.append(edge)

    def affected(self, start: list[str],
                 relations: set[str] | None = None) -> dict[str, Any]:
        """Return dependents of the changed nodes.

        Edges are declared as ``src depends_on / is_checked_by / realizes dst``.
        A change to ``dst`` therefore affects ``src``, so traversal walks the
        incoming edges (reverse dependency direction).
        """
        allowed = relations or RELATIONS
        seen = set(start)
        queue = list(start)
        traversed: list[dict[str, Any]] = []
        while queue:
            current = queue.pop(0)
            for edge in self.edges:
                if edge["to"] != current or edge["relation"] not in allowed:
                    continue
                traversed.append(edge)
                if edge["from"] not in seen:
                    seen.add(edge["from"])
                    queue.append(edge["from"])
        unknown = [node for node in seen
                   if self.nodes.get(node, {}).get("kind") == "unknown"]
        kinds: dict[str, list[str]] = {}
        for node in sorted(seen):
            kind = self.nodes.get(node, {}).get("kind", "unknown")
            kinds.setdefault(kind, []).append(node)
        return {"nodes": sorted(seen), "edges": traversed, "by_kind": kinds,
                "unknown": unknown,
                "limitations": (["图中存在未知节点/关系，按保守回归处理"]
                                if unknown else [])}

    def invalidate(self, start: list[str]) -> dict[str, Any]:
        result = self.affected(start)
        result["invalidated_current_evidence"] = True
        result["historical_results_kept"] = True
        return result

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": list(self.nodes.values()), "edges": list(self.edges)}
