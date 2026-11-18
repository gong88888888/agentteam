"""Trust label shared by the project view and dashboard.

A green run is only ``current_verified`` when the manifest exists, the mode is
formal, DoD passed and runtime acceptance passed. Historical or rehearsal
output is never presented as a current delivery.
"""
from __future__ import annotations

from typing import Any


def project_trust(project: dict[str, Any]) -> str:
    if not project.get("manifest"):
        return "legacy_unverified"
    if str(project.get("mode", "formal")) != "formal":
        return "rehearsal"
    dod = project.get("dod") or {}
    acceptance = project.get("acceptance") or {}
    if dod.get("status") == "pass" and acceptance.get("status") == "pass":
        return "current_verified"
    return "incomplete"
