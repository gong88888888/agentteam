"""Small dependency graph for evidence/verdict invalidation impact."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable


class DependencyGraph:
    def __init__(self) -> None:
        self._forward: dict[str, set[str]] = defaultdict(set)
        self._backward: dict[str, set[str]] = defaultdict(set)

    def add_edge(self, parent: str, child: str) -> None:
        self._forward[parent].add(child)
        self._backward[child].add(parent)

    def add_edges(self, parent: str, children: Iterable[str]) -> None:
        for child in children:
            self.add_edge(parent, child)

    def descendants(self, node: str) -> set[str]:
        seen: set[str] = set()
        q = deque(self._forward.get(node, ()))
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            q.extend(self._forward.get(cur, ()))
        return seen

    def ancestors(self, node: str) -> set[str]:
        seen: set[str] = set()
        q = deque(self._backward.get(node, ()))
        while q:
            cur = q.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            q.extend(self._backward.get(cur, ()))
        return seen

    def nodes(self) -> set[str]:
        return set(self._forward) | set(self._backward)
