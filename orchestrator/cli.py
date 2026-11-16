"""Command line entry points for W1/W2.

Run from the project root:
  python -m orchestrator.cli check-env
  python -m orchestrator.cli skills
  python -m orchestrator.cli demo
  python -m orchestrator.cli judge --packet data/packet.json --rubric code-gate
  python -m orchestrator.cli agent --role product --input brief.txt
  python -m orchestrator.cli canary
  python -m orchestrator.cli eval --offline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .config import ROOT, data_dir, load_config, load_schema, signing_key
from .evidence.store import EvidenceStore
from .evidence.verdict_store import VerdictStore
from .judge.backend import (ModelJudgeBackend, StubJudgeBackend,
                            parse_json_object)
from .judge.panel import JudgePanel
from .judge.packet import build_packet, load_packet, make_evidence
from .judge.rubric import load_rubric
from .judge.canary import run_canary
from .models.router import ModelRouter
from .prompts import load_prompt
from .knowledge import (HybridRetriever, KnowledgeStore, get_embedder,
                        index_project)
from .decisions import DecisionStore
from .skills import SkillRegistry


def build_runtime(args: argparse.Namespace):
    cfg = load_config(getattr(args, "config", None))
    router = ModelRouter(cfg, offline=getattr(args, "offline", False),
                         stub_mode=getattr(args, "stub_mode", "good"))
    key = signing_key()
    ddir = data_dir(cfg)
    evidence = EvidenceStore(ddir / "evidence.jsonl", key)
    verdicts = VerdictStore(ddir / "verdicts.jsonl", key)
    backend = (StubJudgeBackend(mode=getattr(args, "stub_mode", "good"))
               if getattr(args, "offline", False)
               else ModelJudgeBackend(router,
                                      allow_local=getattr(args, "allow_local_judge", False)))
    panel = JudgePanel(backend, store=verdicts,
                       conservative=getattr(args, "conservative", False))
    skills = SkillRegistry.load(ROOT / "skills" / "registry.yaml")
    return cfg, router, evidence, verdicts, backend, panel, skills


def cmd_check_env(args: argparse.Namespace) -> int:
    cfg, router, evidence, verdicts, backend, panel, skills = build_runtime(args)
    report = {
        "project_root": str(ROOT),
        "config": "config/config.yaml" if (ROOT / "config" / "config.yaml").exists()
                  else "config/config.example.yaml",
        "models": router.available_report(),
        "judge": {
            "offline": args.offline,
            "allow_local_judge": getattr(args, "allow_local_judge", False),
            "ready": args.offline or router.deepseek.available(),
            "note": "未配置 DEEPSEEK_API_KEY 时裁判默认失败关闭；可用 --offline 或 --allow-local-judge 做本地预演",
        },
        "signing_key_file": str(ROOT / ".agentteam" / "signing.key"),
        "ledgers": {
            "evidence": str(evidence.path),
            "verdicts": str(verdicts.path),
            "evidence_chain_ok": evidence.verify_chain(),
            "verdict_chain_ok": verdicts.verify_chain(),
        },
        "skills": skills.report(),
        "schemas": [n for n in ("task-card.schema.json", "evidence.schema.json",
                                "decision-packet.schema.json", "verdict.schema.json",
                                "agent-output.schema.json", "agent-spec.schema.json")
                    if (ROOT / "specs" / n).exists()],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not skills.errors else 1


def cmd_skills(args: argparse.Namespace) -> int:
    skills = SkillRegistry.load(ROOT / "skills" / "registry.yaml")
    if args.role:
        print(json.dumps([{"name": s.name, "path": s.relative(),
                           "description": s.description}
                          for s in skills.for_role(args.role)],
                         ensure_ascii=False, indent=2))
    else:
        print(json.dumps(skills.report(), ensure_ascii=False, indent=2))
    return 0 if not skills.errors else 1


def _sample_packet() -> dict[str, Any]:
    checks = [make_evidence(k, evidence_id=f"EV-{i:04d}")
              for i, k in enumerate(("unit", "lint", "typecheck",
                                     "contract_test", "out_of_scope", "sast"), 1)]
    return build_packet(
        gate_id="G-CODE-S2", decision_type="gate",
        scope={"project": "demo", "slice": "S2", "risk": "high"},
        baseline_versions={"product": "v1.1", "arch": "v1.0"},
        baseline_fp="baseline-demo", subject_hash="subject-demo",
        inputs=[{"path": "src/backend/s2/main.py", "sha256": "subject-demo",
                 "signed_by": "tool:fs"}],
        checks=checks, missing_evidence=[], acceptance=["AC-2"],
        diff={"out_of_scope_writes": 0},
        risk={"level": "high", "factors": ["auth"]},
        claims=[{"claim": "已修复越权", "signed_by": "agent:backend"}])


def cmd_demo(args: argparse.Namespace) -> int:
    _, _, _, _, backend, panel, _ = build_runtime(args)
    rubric = load_rubric("code-gate")
    packet = _sample_packet()
    result = panel.decide(packet, rubric)
    print(json.dumps({"good_packet": result.verdict,
                      "panel_trace": result.trace}, ensure_ascii=False, indent=2))
    bad = dict(packet)
    bad["deterministic_checks"] = [c for c in packet["deterministic_checks"]
                                   if c["kind"] != "contract_test"]
    bad["missing_evidence"] = ["contract_test"]
    bad["packet_hash"] = None
    from .judge.packet import packet_hash
    bad["packet_hash"] = packet_hash(bad)
    result2 = panel.decide(bad, rubric)
    print(json.dumps({"bad_packet": result2.verdict,
                      "panel_trace": result2.trace}, ensure_ascii=False, indent=2))
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    _, _, _, _, backend, panel, _ = build_runtime(args)
    packet = load_packet(args.packet)
    rubric = load_rubric(args.rubric)
    try:
        result = panel.decide(packet, rubric)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "fail_closed": True},
                         ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"verdict": result.verdict,
                      "panel_trace": result.trace}, ensure_ascii=False, indent=2))
    return 0 if result.verdict["decision"] in ("approve", "approve_with_conditions") else 1


def cmd_canary(args: argparse.Namespace) -> int:
    _, _, _, _, backend, panel, _ = build_runtime(args)
    report = run_canary(backend, load_rubric("code-gate"),
                        max_cases=args.max_cases, panel=panel)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["miss_rate"] <= 0.10 else 1


def _agent_spec(role: str) -> dict[str, Any]:
    doc = yaml.safe_load((ROOT / "specs" / "agent-specs.yaml").read_text(encoding="utf-8"))
    for spec in doc["specs"]:
        if spec["id"] == role:
            return spec
    raise SystemExit(f"未知角色：{role}")


def _agent_prompt(role: str) -> str:
    return load_prompt(role).text


def cmd_agent(args: argparse.Namespace) -> int:
    cfg, router, _, _, _, _, _ = build_runtime(args)
    prompt = load_prompt(args.role)
    text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
    messages = [{"role": "system", "content": prompt.text},
                {"role": "user", "content": text}]
    schema = load_schema("agent-output.schema.json")
    last = None
    for _ in range(2):
        result = router.execution(args.role, messages, response_format="json")
        try:
            obj = parse_json_object(result.content)
            jsonschema.validate(obj, schema)
            print(json.dumps({"output": obj,
                              "prompt": prompt.metadata(),
                              "model": result.model,
                              "backend": result.backend,
                              "latency_ms": result.latency_ms,
                              "tokens": result.prompt_tokens + result.completion_tokens},
                             ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            last = exc
            messages += [
                {"role": "assistant", "content": result.content},
                {"role": "user", "content": f"输出不符合 agent-output schema：{exc}。只输出合法 JSON。"},
            ]
    print(json.dumps({"error": f"Agent 输出两次不合法：{last}"},
                     ensure_ascii=False, indent=2))
    return 1


def cmd_kb_index(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db = data_dir(cfg) / "knowledge.db"
    store = KnowledgeStore(db)
    embedder = get_embedder(cfg, args.backend)
    paths = None
    if args.paths:
        paths = [Path(p) for p in args.paths.split(",") if p]
    result = index_project(store, embedder, paths, ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_kb_query(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db = data_dir(cfg) / "knowledge.db"
    if not db.exists():
        print(json.dumps({"error": "知识库未索引，请先运行 kb-index"},
                         ensure_ascii=False))
        return 2
    retriever = HybridRetriever(db, cfg)
    hits = retriever.search(args.query, top_k=args.top_k,
                            source_type=args.source_type,
                            path_prefix=args.path_prefix)
    if args.json:
        print(json.dumps({"query": args.query, "hits": hits,
                          "stats": retriever.stats()}, ensure_ascii=False, indent=2))
        return 0
    print(f"query: {args.query}")
    for h in hits:
        if "warnings" in h:
            print("warning:", h["warnings"])
            continue
        print(f"- {h['score']:.4f}  {h['citation']}")
        print(f"    {h['text'][:180].replace(chr(10), ' ')}")
    return 0


def cmd_kb_stats(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    db = data_dir(cfg) / "knowledge.db"
    if not db.exists():
        print(json.dumps({"error": "知识库未索引"}, ensure_ascii=False))
        return 2
    print(json.dumps(KnowledgeStore(db).stats(), ensure_ascii=False, indent=2))
    return 0


def cmd_decisions(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    store = DecisionStore(data_dir(cfg) / "decisions.db")
    store.seed_demo()
    if args.action in ("list",):
        status = None if args.status == "all" else args.status
        print(json.dumps({"decisions": store.list(status), "stats": store.stats()},
                         ensure_ascii=False, indent=2))
        return 0
    if not args.id:
        raise SystemExit("需要 --id")
    if args.action == "show":
        item = store.get(args.id)
        if not item:
            raise SystemExit(f"决策不存在：{args.id}")
        print(json.dumps(item, ensure_ascii=False, indent=2))
        return 0
    mapping = {"approve": "approve", "approve-conditions": "approve_with_conditions",
               "reject": "reject", "defer": "defer",
               "request-evidence": "request_evidence"}
    item = store.decide(args.id, mapping[args.action], args.reason or "",
                        args.actor or "policy-owner")
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from eval.run_eval import run
    # eval defaults to offline for CI; pass --real to call local Qwen/DeepSeek.
    return run(offline=not args.real, allow_local_judge=args.allow_local_judge,
               limit=args.limit, config=args.config)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AgentTeam W1/W2 CLI")
    p.add_argument("--config", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    def common(name: str, help_text: str):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--config", default=None)
        sp.add_argument("--offline", action="store_true",
                        help="使用确定性 stub，不调用网络模型")
        sp.add_argument("--stub-mode", default="good",
                        choices=["good", "timeout", "schema_error", "rubber_stamp"])
        sp.add_argument("--allow-local-judge", action="store_true",
                        help="裁判允许降级到本地 Qwen（会记录 family collision）")
        sp.add_argument("--conservative", action="store_true")
        return sp

    common("check-env", "检查本地 Qwen、DeepSeek、账本、技能与 Schema")
    sp = common("skills", "列出本地技能或某角色的技能")
    sp.add_argument("--role", default=None)
    common("demo", "用 stub 跑一个通过/补证的门禁示例")
    sp = common("judge", "对决策包运行 J1/J2/J3 裁判")
    sp.add_argument("--packet", required=True)
    sp.add_argument("--rubric", default="code-gate")
    sp = common("canary", "运行金丝雀坏样本，检查漏判率")
    sp.add_argument("--max-cases", type=int, default=None)
    sp = common("agent", "用本地 Qwen（或 DeepSeek 补充）执行一个 Agent")
    sp.add_argument("--role", required=True)
    sp.add_argument("--input", default=None, help="输入文件；省略则读 stdin")
    sp = common("eval", "运行 W2 离线/真实评测（默认离线）")
    sp.add_argument("--limit", type=int, default=None)
    sp.add_argument("--real", action="store_true",
                    help="调用本地 Qwen；裁判需要 DeepSeek 或 --allow-local-judge")

    sp = sub.add_parser("decisions", help="决策收件箱：列表/查看/审批")
    sp.add_argument("action", choices=["list", "show", "approve",
                                        "approve-conditions", "reject",
                                        "defer", "request-evidence"])
    sp.add_argument("--id", default=None)
    sp.add_argument("--reason", default="")
    sp.add_argument("--actor", default="policy-owner")
    sp.add_argument("--status", default="pending",
                    choices=["pending", "all", "decided"])
    sp.add_argument("--config", default=None)

    sp = sub.add_parser("kb-index", help="索引项目文档到本地混合检索知识库")
    sp.add_argument("--config", default=None)
    sp.add_argument("--backend", choices=["auto", "hash", "ollama"], default="auto")
    sp.add_argument("--paths", default=None, help="逗号分隔的文件/目录；省略则索引默认文档")
    sp = sub.add_parser("kb-query", help="混合检索知识库")
    sp.add_argument("query")
    sp.add_argument("--config", default=None)
    sp.add_argument("--top-k", type=int, default=8)
    sp.add_argument("--source-type", default=None)
    sp.add_argument("--path-prefix", default=None)
    sp.add_argument("--json", action="store_true")
    sp = sub.add_parser("kb-stats", help="知识库统计")
    sp.add_argument("--config", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "check-env":
        return cmd_check_env(args)
    if args.command == "skills":
        return cmd_skills(args)
    if args.command == "demo":
        return cmd_demo(args)
    if args.command == "judge":
        return cmd_judge(args)
    if args.command == "canary":
        return cmd_canary(args)
    if args.command == "agent":
        return cmd_agent(args)
    if args.command == "eval":
        return cmd_eval(args)
    if args.command == "decisions":
        return cmd_decisions(args)
    if args.command == "kb-index":
        return cmd_kb_index(args)
    if args.command == "kb-query":
        return cmd_kb_query(args)
    if args.command == "kb-stats":
        return cmd_kb_stats(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())