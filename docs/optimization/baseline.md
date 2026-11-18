# Optimization Baseline (T00)

Recorded before any code change, per the 2026-11-18 optimization plan.

## Repository

| Item | Value |
|---|---|
| Remote branch | `v4.1-protocol-fixes` |
| Baseline commit | `afbfaab7e0e290373722b811bbfe536606511411` |
| Baseline date | 2026-11-18 |
| Working tree at start | clean except untracked `optimization-2026-11-18/` and its zip |
| Main branch | `main` |

## Runtime

| Item | Value |
|---|---|
| OS | Windows 10 Pro build 19045 |
| Python | 3.13.15 |
| Node | v25.2.1 |
| npm | 11.6.2 |
| Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe` |
| Shell | Git Bash (POSIX sh) |
| Config | `config/config.example.yaml` (no local `config.yaml`) |
| Secrets | not printed; read via env / Windows user env |

The audit report used Python 3.12. This machine runs 3.13.15; all commands below use 3.13.

## Existing test baseline

```
python -m unittest discover -s tests -v
Ran 30 tests in 4.800s
OK
```

All 30 tests passed before changes. This is a regression baseline, not proof of
product acceptance.

## Known audit counterexamples (from `optimization-2026-11-18/audit-probes.json`)

| Probe | Baseline result | Required result |
|---|---|---|
| P01 invalid source + blocked review | pass | fail |
| P02 incomplete web DoD | pass | fail |
| P03 empty product document | pass | fail |
| P04 unverified evidence dictionaries | pass | reject at trust boundary |
| P05 stale review gates | pass | fail |
| P06 unknown backend | stub | configuration error |
| P07 heading ID shift | SRC-002 → SRC-003 | stable identity / explicit move |
| P08 generated game module reachability | 13 modules unreachable | integration gate fails |

## Scope and constraints

- Do not delete or rewrite user content, history or the existing evidence ledger.
- Preserve the 30 passing tests; where a behavior is intentionally tightened,
  add a replacement test that asserts the new, safer behavior.
- New capabilities are deterministic and offline-testable. Real model calls are
  optional and never required for the CI path.
- No secrets or full environment dumps are written to project artifacts.
- Each round produces its own test evidence and a record in
  [rounds.md](rounds.md).

## Round plan

1. Trust boundaries: strict routing, review status/refs, coverage provenance.
2. Attempt identity, artifact provenance, verified evidence consumption.
3. Iteration manifest, web runtime acceptance, stage blocking.
4. Model response protocol, source units, requirement ledger, context assembler.
5. Game extension registry and reachability/integration acceptance.
6. SQLite tasks/attempts, leases, outbox, minimal tool loop.
7. Findings, independent QA, iteration controller, actions, impact, knowledge.
8. Capability probes, failure-injection acceptance suite, docs/dashboard, full regression.
