# Optimization Execution Log

Baseline: `afbfaab7e0e290373722b811bbfe536606511411`.
Plan: 8 rounds covering task cards T00–T31 from `optimization-2026-11-18/11` and `12`.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` implemented and verified.

## Round 1 — Trust boundaries — DONE

- [x] T00 baseline record (`baseline.md`) and this log
- [x] T01 reject unknown model backend; explicit offline-only stub
- [x] T02 review status cannot default to success; source refs validated
- [x] T03 coverage only from registered current-run artifacts
- Evidence: `tests/test_optimization_round1.py` (12 tests); P01/P05/P06/P07 paths.

## Round 2 — Attempt identity, artifacts, evidence — DONE

- [x] T04 current review gate set bound to run/source/attempt, failure supersedes old pass
- [x] T05 empty and runner-summary artifacts rejected; sandbox files checked in workspace
- [x] T06 `EvidenceResolver` at the gate trust boundary (signature, expiry, revocation, subject, kind)
- Evidence: `tests/test_optimization_round2.py` (13 tests); existing gate tests updated to signed evidence.

## Round 3 — Plan, runtime acceptance, stage blocking — DONE

- [x] T07 iteration manifest drives the required DoD set; no manifest → `legacy_incomplete`
- [x] T08 web runtime acceptance plugin (start, health, business flow, signed evidence)
- [x] T09 formal mode blocks downstream after a failed stage; rehearsal cannot complete
- Evidence: `tests/test_optimization_round3.py` (11 tests); minimal-api template now exposes `/api/v1/exports/csv`.

## Round 4 — Protocol, sources, requirements, context — DONE

- [x] T11 model response object: tool calls, finish reason, usage, provider metadata, error taxonomy
- [x] T12 source units with stable identity, content hash and diff (added/removed/changed/moved/uncertain)
- [x] T13 atomic requirements, source dispositions, validation and Markdown rendering
- [x] T14 design state and transition checks
- [x] T15 context assembler replaces fixed summary truncation; manifest records injected items
- Evidence: `tests/test_optimization_round4.py` (22 tests); product review writes `source-units.json`, `source-diff.json`, requirement ledgers.

## Round 5 — Game integration — DONE

- [x] T10 extension registry, manifest, reachability and loaded/invoked/asserted harness
- [x] Template registry + `tests/integration.mjs`; runner auto-registers modules with metadata
- [x] test1 example: 14 modules registered and exercised; pre-existing broken `player.js` imports fixed
- Evidence: `tests/test_optimization_round5.py` (8 tests); `projects/test1/acceptance.json` 7/7 with integration.

## Round 6 — Persistence, concurrency, tool loop — DONE

- [x] T17 SQLite project/iteration/task/attempt/artifact store
- [x] T18 leases, heartbeat, orphan recovery, CAS completion
- [x] T19 transactional outbox and idempotent consumers
- [x] T16 minimal tool loop: read/list/search/patch/run_check/submit with path, scope and budget checks
- Evidence: `tests/test_optimization_round6.py` (15 tests); every project run writes `state/agentteam.db`.

## Round 7 — Feedback and iteration control — DONE

- [x] T20 finding schema, root-cause routing, dedupe and repair tasks
- [x] T21 independent QA verification; self-verification and unverified pass rejected
- [x] T22 iteration controller: pause/resume, budget stop, verification backlog, idle state
- [x] T23 retrospective action becomes a task; vague advice stays candidate
- [x] T24 knowledge authority levels, review/activate/revoke, candidate excluded by default
- [x] T25 typed impact graph with reverse-dependent traversal and unknown-node limitations
- Evidence: `tests/test_optimization_round7.py` (19 tests).

## Round 8 — Acceptance, evaluation, handover — DONE

- [x] T26 capability probe (offline contract + explicit real opt-in) and model identity records
- [x] T29 20-case deterministic failure-injection suite
- [x] T27 high-risk role judge gate (deterministic gate first; judge can only block)
- [x] T28 project trust labels (`current_verified` / `rehearsal` / `incomplete` / `legacy_unverified`) in project state, live feed and dashboard
- [x] New schemas: iteration manifest, source unit, requirement, source disposition
- [x] CI: unit tests, failure injection, capability probe, selfcheck, evaluations, simulators, specs
- Evidence: `tests/test_optimization_round8.py` (16 tests), `eval/out/failure-injection.json` 20/20.

## Final verification (2026-11-18)

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | **146 tests OK** |
| `python eval/failure_injection.py` | **20/20 passed** |
| `python -m orchestrator.selfcheck` | ALL CHECKS PASSED |
| `python eval/run_eval.py --offline` | exit 0, judge 11/11, canary 7/7, agents 6/6, revalidation 4/4 |
| `python eval/role_eval.py --offline --full` | exit 0, 24/24, full_coverage=true |
| `python eval/prompt_regression.py --offline` | regressed=false |
| `python eval/kb_eval.py` | 22 cases, recall@5 22/22 |
| `python -I sim/selfcheck.py` | ALL CHECKS PASSED |
| `python -I sim/w3_selfcheck.py` | ALL CHECKS PASSED (dashboard assertion updated to current title) |
| `python -I specs/validate_specs.py` | 12 specs, 11 schemas OK |
| `python -m orchestrator.cli model-capabilities --offline` | exit 0, contract pass, simulation=true |
| `projects/test1` game acceptance | 7/7 pass; 14 extensions loaded/invoked/asserted |
| test1 真实浏览器 | `window.__AGENTTEAM_EXTENSIONS__` loaded=14, init 全部 ok；游戏菜单渲染正常 |
| Dashboard | trust label visible (`legacy_unverified` for test1, correct for new runs) |
