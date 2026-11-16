"""Configuration, paths and signing-key handling.

Secrets are never stored in config/config.yaml. The resolution order is:
  1. environment variable
  2. .agentteam/signing.key (created locally, 0600 where supported)
"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"
EXAMPLE_CONFIG_PATH = ROOT / "config" / "config.example.yaml"
DEFAULT_LOCAL_MODEL = "qwen3.6:35b-a3b-mtp-q4_K_M"
DEFAULT_LOCAL_FALLBACK = "qwen3.5:9b-q4_K_M"


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    p = Path(path) if path else (CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH)
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("runtime", {})
    cfg.setdefault("models", {})
    cfg.setdefault("approval", {})
    cfg.setdefault("execution", {})
    cfg.setdefault("skills", {})
    _apply_env(cfg)
    return cfg


def _apply_env(cfg: dict[str, Any]) -> None:
    models = cfg.setdefault("models", {})
    local = models.setdefault("local", {})
    local["base_url"] = os.environ.get("OLLAMA_BASE_URL", local.get("base_url", "http://localhost:11434"))
    local["model"] = os.environ.get("LOCAL_MODEL", local.get("model", DEFAULT_LOCAL_MODEL))
    fallback = os.environ.get("LOCAL_FALLBACK_MODEL")
    if fallback:
        local["fallback_models"] = [fallback]
    local.setdefault("fallback_models", [DEFAULT_LOCAL_FALLBACK])
    local.setdefault("timeout_s", 120)
    local.setdefault("think", False)

    ds = models.setdefault("deepseek", {})
    ds["base_url"] = os.environ.get(
        "DEEPSEEK_HARNESS_URL", ds.get("base_url", "https://api.deepseek.com/v1"))
    ds["api_key"] = os.environ.get("DEEPSEEK_API_KEY", ds.get("api_key", ""))
    ds["model"] = os.environ.get("DEEPSEEK_CHAT_MODEL", ds.get("model", "deepseek-chat"))
    ds["reasoner"] = os.environ.get("DEEPSEEK_REASONER_MODEL", ds.get("reasoner", "deepseek-reasoner"))
    ds.setdefault("chat_path", "/chat/completions")
    ds.setdefault("timeout_s", 120)
    ds.setdefault("price_in_per_m", 0.5)
    ds.setdefault("price_out_per_m", 1.5)

    models.setdefault("routing", {
        "pm": {"primary": "local", "fallback": "deepseek"},
        "product": {"primary": "local", "fallback": "deepseek"},
        "ui": {"primary": "local", "fallback": "deepseek"},
        "arch": {"primary": "local", "fallback": "deepseek"},
        "frontend": {"primary": "local", "fallback": "deepseek"},
        "backend": {"primary": "local", "fallback": "deepseek"},
        "review": {"primary": "local", "fallback": "deepseek"},
        "qa": {"primary": "local", "fallback": "deepseek"},
        "security": {"primary": "local", "fallback": "deepseek"},
        "ops": {"primary": "local", "fallback": "deepseek"},
        "kb": {"primary": "local", "fallback": "deepseek"},
        "retro": {"primary": "local", "fallback": "deepseek"},
        "judge_j1": {"primary": "deepseek", "fallback": "local"},
        "judge_j2": {"primary": "local", "fallback": "deepseek"},
        "judge_j3": {"primary": "deepseek", "fallback": "local"},
    })

    skills = cfg.setdefault("skills", {})
    skills.setdefault("registry", "skills/registry.yaml")
    skills.setdefault("root", "RAG-Agent-Toolkit/agent-toolkit/skills")


def data_dir(cfg: dict[str, Any]) -> Path:
    p = ROOT / cfg.get("runtime", {}).get("data_dir", "data")
    p.mkdir(parents=True, exist_ok=True)
    return p


def signing_key() -> bytes:
    env = os.environ.get("EVIDENCE_SIGNING_KEY")
    if env:
        return env.encode("utf-8")
    key_path = ROOT / ".agentteam" / "signing.key"
    if key_path.exists():
        raw = key_path.read_bytes().strip()
        if raw:
            return raw
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


def load_schema(name: str) -> dict[str, Any]:
    path = ROOT / "specs" / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def schema_path(name: str) -> Path:
    return ROOT / "specs" / name
