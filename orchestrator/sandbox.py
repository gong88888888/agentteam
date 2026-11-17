"""Process-level sandbox and isolated workspaces for generated code.

This is deliberately not a container. It provides:
  - an executable allowlist and argv-only execution (no shell);
  - a scrubbed environment that never inherits API keys;
  - a pinned working directory, timeout and bounded output;
  - an isolated copy/worktree of the project for code-role writes.

Kernel-level isolation (containers, seccomp, network namespaces) belongs to the
deployment environment; this layer is the portable, testable part.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ALLOWLIST = (
    "python", "python3", "pytest", "unittest", "node", "npm", "npx",
    "semgrep", "trivy", "schemathesis", "git",
)

SHELL_METACHARS = re.compile(r"[;&|><`$()\r\n]")
COPY_DIRS = ("docs", "src", "tests", "contracts", "scripts", "knowledge", "tools", "game")
COPY_FILES = ("README.md", "pyproject.toml", "requirements.txt", "package.json")
IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", ".pytest_cache", "node_modules",
    "artifacts", "logs", "state", "evidence", "quality",
)


class SandboxError(RuntimeError):
    """Raised when a command or path violates the sandbox policy."""


def _norm_exe(value: str) -> str:
    name = Path(value).name.lower()
    return name[:-4] if name.endswith(".exe") else name


def safe_relative(path: str | Path) -> str:
    rel = Path(str(path).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise SandboxError(f"非法相对路径：{path}")
    return rel.as_posix()


def tree_hash(root: str | Path, *, subdirs: Iterable[str] | None = None) -> str:
    """Stable hash of project sources/tests/contracts (not logs or artifacts)."""
    root = Path(root).resolve()
    names = tuple(subdirs) if subdirs else COPY_DIRS
    h = hashlib.sha256()
    for name in names:
        base = root / name
        if not base.exists():
            continue
        files = [base] if base.is_file() else sorted(
            p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for p in files:
            rel = p.relative_to(root).as_posix()
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    for name in COPY_FILES:
        p = root / name
        if p.is_file():
            h.update(name.encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


@dataclass
class CommandResult:
    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    cwd: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        return {
            "argv": self.argv, "exit_code": self.exit_code,
            "duration_ms": self.duration_ms, "timed_out": self.timed_out,
            "stdout_sha256": hashlib.sha256(self.stdout.encode("utf-8")).hexdigest(),
            "stderr_tail": self.stderr[-1200:], "stdout_tail": self.stdout[-1200:],
        }


@dataclass
class Sandbox:
    root: str | Path
    allowlist: Sequence[str] = DEFAULT_ALLOWLIST
    timeout_s: int = 180
    max_output: int = 200_000
    _allow: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        if not self.root.is_dir():
            raise SandboxError(f"沙箱根目录不存在：{self.root}")
        self._allow = tuple(_norm_exe(a) for a in self.allowlist)

    def validate(self, argv: Sequence[str]) -> list[str]:
        if not argv or not all(isinstance(a, str) and a for a in argv):
            raise SandboxError("命令必须是非空字符串 argv")
        if any(SHELL_METACHARS.search(a) for a in argv):
            raise SandboxError("命令参数包含 shell 元字符")
        exe = _norm_exe(argv[0])
        if exe not in self._allow:
            raise SandboxError(f"可执行文件不在允许列表：{exe}")
        return list(argv)

    def _cwd(self, cwd: str | Path | None) -> Path:
        base = self.root if cwd is None else (self.root / safe_relative(cwd))
        base = base.resolve()
        if base != self.root and not str(base).startswith(str(self.root) + os.sep):
            raise SandboxError(f"工作目录越界：{base}")
        if not base.is_dir():
            raise SandboxError(f"工作目录不存在：{base}")
        return base

    def _env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME") or os.environ.get("USERPROFILE", ""),
            "TMP": os.environ.get("TMP", tempfile.gettempdir()),
            "TEMP": os.environ.get("TEMP", tempfile.gettempdir()),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "COMSPEC": os.environ.get("COMSPEC", ""),
            "PATHEXT": os.environ.get("PATHEXT", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "CI": "1",
        }
        if extra:
            for k, v in extra.items():
                if k.lower().endswith(("key", "token", "secret", "password")):
                    continue
                env[k] = str(v)
        return env

    def run(self, argv: Sequence[str], *, cwd: str | Path | None = None,
            extra_env: dict[str, str] | None = None) -> CommandResult:
        argv = self.validate(argv)
        cwd_path = self._cwd(cwd)
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                argv, cwd=str(cwd_path), env=self._env(extra_env),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=self.timeout_s, shell=False,
            )
            stdout, stderr = proc.stdout or "", proc.stderr or ""
            code, timed_out = proc.returncode, False
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            code, timed_out = 124, True
        return CommandResult(
            argv=argv, exit_code=code,
            stdout=stdout[: self.max_output], stderr=stderr[: self.max_output],
            duration_ms=int((time.perf_counter() - started) * 1000),
            timed_out=timed_out, cwd=str(cwd_path),
        )


class IsolatedWorkspace:
    """Per-role workspace: a git worktree when possible, otherwise a copy.

    Writes land in ``path``; ``promote`` copies approved files back to the
    project root. Cleanup always removes the worktree/copy.
    """

    def __init__(self, project_dir: str | Path, name: str, *,
                 use_git: bool = True) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.name = safe_relative(name).replace("/", "-")
        self.use_git = use_git
        self.path: Path | None = None
        self.mode = "copy"

    def __enter__(self) -> "IsolatedWorkspace":
        base = Path(tempfile.mkdtemp(prefix=f"agentteam-{self.name}-"))
        target = base / "workspace"
        if self.use_git and (self.project_dir / ".git").exists() and shutil.which("git"):
            proc = subprocess.run(
                ["git", "-C", str(self.project_dir), "worktree", "add",
                 "--detach", str(target), "HEAD"],
                capture_output=True, text=True, timeout=60, shell=False)
            if proc.returncode == 0:
                self.path, self.mode = target, "git-worktree"
                return self
            shutil.rmtree(base, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
        for d in COPY_DIRS:
            src = self.project_dir / d
            if src.is_dir():
                shutil.copytree(src, target / d, ignore=IGNORE)
        for f in COPY_FILES:
            src = self.project_dir / f
            if src.is_file():
                shutil.copyfile(src, target / f)
        self.path = target
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        if not self.path:
            return
        if self.mode == "git-worktree":
            subprocess.run(["git", "-C", str(self.project_dir), "worktree", "remove",
                            "--force", str(self.path)],
                           capture_output=True, text=True, timeout=60, shell=False)
            subprocess.run(["git", "-C", str(self.project_dir), "worktree", "prune"],
                           capture_output=True, text=True, timeout=30, shell=False)
        parent = self.path.parent
        shutil.rmtree(parent, ignore_errors=True)
        self.path = None

    def promote(self, paths: Iterable[str]) -> list[str]:
        if not self.path:
            raise SandboxError("workspace 未创建")
        promoted = []
        for raw in paths:
            rel = safe_relative(raw)
            src = (self.path / rel).resolve()
            if not src.is_file():
                continue
            target = (self.project_dir / rel).resolve()
            root = str(self.project_dir)
            if target != Path(root) and not str(target).startswith(root + os.sep):
                raise SandboxError(f"提升路径越界：{rel}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            promoted.append(rel)
        return promoted
