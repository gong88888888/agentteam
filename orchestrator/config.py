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


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _windows_user_env(names: tuple[str, ...]) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            for name in names:
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except OSError:
                    continue
                if value:
                    return os.path.expandvars(str(value))
    except OSError:
        return ""
    return ""


def env_value(*names: str) -> str:
    """Look up env aliases case-insensitively, then Windows User env."""
    wanted = {n.lower().replace("-", "_") for n in names}
    for k, v in os.environ.items():
        if k.lower().replace("-", "_") in wanted and v:
            return v
    return _windows_user_env(names)


def deepseek_api_key() -> str:
    return env_value("DEEPSEEK_API_KEY", "DEEPSEEK_KEY1", "DEEPSEEK_KEY_1",
                     "DEEPSEEK_KEY", "deepseek-key1")


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    _load_dotenv()
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
    local["base_url"] = env_value("OLLAMA_BASE_URL") or local.get("base_url", "http://localhost:11434")
    local["model"] = env_value("LOCAL_MODEL") or local.get("model", DEFAULT_LOCAL_MODEL)
    fallback = env_value("LOCAL_FALLBACK_MODEL")
    if fallback:
        local["fallback_models"] = [fallback]
    local.setdefault("fallback_models", [DEFAULT_LOCAL_FALLBACK])
    local.setdefault("timeout_s", 120)
    local.setdefault("think", False)
    local.setdefault("num_ctx", 32768)

    ds = models.setdefault("deepseek", {})
    ds["base_url"] = (env_value("DEEPSEEK_HARNESS_URL")
                      or ds.get("base_url", "https://api.deepseek.com/v1"))
    ds["api_key"] = deepseek_api_key() or ds.get("api_key", "")
    ds["model"] = (env_value("DEEPSEEK_CHAT_MODEL")
                   or ds.get("model", "deepseek-chat"))
    ds["reasoner"] = (env_value("DEEPSEEK_REASONER_MODEL")
                      or ds.get("reasoner", "deepseek-reasoner"))
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
    env = env_value("EVIDENCE_SIGNING_KEY")
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
