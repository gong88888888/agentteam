"""Iteration manifest: the committed scope that Definition of Done checks.

The required set comes from the approved iteration, never from whichever roles
happen to exist in ``state/roles.json``. An old project without a manifest is
``legacy_incomplete`` until it is explicitly re-verified.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..process import stage_plan


@dataclass
class ManifestItem:
    id: str
    role: str
    stage: str
    required: bool = True
    acceptance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role, "stage": self.stage,
                "required": self.required, "acceptance": self.acceptance}


@dataclass
class IterationManifest:
    project_id: str
    iteration_id: str
    project_type: str
    profile: str
    delivery_kind: str
    requires_entry: bool
    entry: str = ""
    required_tasks: list[ManifestItem] = field(default_factory=list)
    required_acceptance: list[str] = field(default_factory=list)
    required_docs: list[str] = field(default_factory=list)
    required_reviews: list[str] = field(default_factory=list)
    required_decisions: list[str] = field(default_factory=list)
    mode: str = "formal"
    budget: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    schema_version: str = "1.0"

    @property
    def required_roles(self) -> list[str]:
        return [t.role for t in self.required_tasks if t.required]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "iteration_id": self.iteration_id,
            "project_type": self.project_type,
            "profile": self.profile,
            "delivery_kind": self.delivery_kind,
            "requires_entry": self.requires_entry,
            "entry": self.entry,
            "required_tasks": [t.to_dict() for t in self.required_tasks],
            "required_acceptance": self.required_acceptance,
            "required_docs": self.required_docs,
            "required_reviews": self.required_reviews,
            "required_decisions": self.required_decisions,
            "mode": self.mode,
            "budget": self.budget,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IterationManifest":
        tasks = [ManifestItem(**t) for t in data.get("required_tasks") or []]
        return cls(
            project_id=str(data.get("project_id", "")),
            iteration_id=str(data.get("iteration_id", "")),
            project_type=str(data.get("project_type", "web")),
            profile=str(data.get("profile", "basic")),
            delivery_kind=str(data.get("delivery_kind", "software")),
            requires_entry=bool(data.get("requires_entry", True)),
            entry=str(data.get("entry", "")),
            required_tasks=tasks,
            required_acceptance=list(data.get("required_acceptance") or []),
            required_docs=list(data.get("required_docs") or []),
            required_reviews=list(data.get("required_reviews") or []),
            required_decisions=list(data.get("required_decisions") or []),
            mode=str(data.get("mode", "formal")),
            budget=dict(data.get("budget") or {}),
            created_at=float(data.get("created_at", time.time())),
            schema_version=str(data.get("schema_version", "1.0")),
        )


def build_manifest(*, project_id: str, iteration_id: str, project_type: str,
                   roles: list[str], template: str, profile: str,
                   mode: str = "formal") -> IterationManifest:
    plan = stage_plan(project_type)
    stage_of: dict[str, str] = {}
    for stage in plan:
        for role in stage["roles"]:
            stage_of[role] = stage["id"]
    tasks = [ManifestItem(id=f"T-{role.upper()}", role=role,
                          stage=stage_of.get(role, "unassigned"))
             for role in roles]
    code_roles = {"backend", "frontend"}
    requires_entry = (
        project_type == "game"
        or template in ("minimal-api", "web-2d-game")
        or any(r in code_roles for r in roles)
    )
    docs: list[str] = []
    if "product" in roles:
        docs.append("docs/product/product-baseline.md")
    if "arch" in roles:
        docs.append("docs/architecture/architecture.md")
    if project_type == "game":
        acceptance = ["entry", "logic", "smoke", "integration", "render"]
        entry = "game/index.html"
        delivery_kind = "game-slice"
    else:
        acceptance = ["web_start", "web_health", "web_flow"] if requires_entry else []
        entry = "src/backend/app.py"
        delivery_kind = "software" if requires_entry else "documentation"
    return IterationManifest(
        project_id=project_id, iteration_id=iteration_id,
        project_type=project_type, profile=profile, delivery_kind=delivery_kind,
        requires_entry=requires_entry, entry=entry,
        required_tasks=tasks, required_acceptance=acceptance,
        required_docs=docs, mode=mode,
        budget={"max_attempts_per_task": 2})


def manifest_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / "state" / "manifest.json"


def write_manifest(project_dir: str | Path, manifest: IterationManifest) -> Path:
    path = manifest_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def load_manifest(project_dir: str | Path) -> IterationManifest | None:
    path = manifest_path(project_dir)
    try:
        return IterationManifest.from_dict(
            json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
