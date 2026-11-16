---
name: postmortem-to-tests
description: Convert engineering incident postmortems into standardized structured analysis plus actionable regression test cases. Use when the user provides an incident log, outage description, failure report, production bug postmortem draft, alert record, deployment/change record, or error stack trace and wants root-cause analysis and regression coverage. Triggers on "postmortem", "incident", "outage", "production bug", "failure report", "root cause", "regression test", "detection gap", "residual risk", or a pasted incident narrative. Enforces a fixed 6-stage workflow and an unchangeable output template.
license: MIT
---

# Postmortem To Tests

Turn an incident postmortem into (1) a standardized structured analysis and (2) concrete, actionable regression test cases — so the same failure class cannot silently return.

## When to Use

Trigger this skill when the user supplies any of:
- Incident logs / outage descriptions / failure reports
- Production bug postmortem drafts
- Alert records / on-call notes
- Deployment or config change records
- Error stack traces tied to a user-visible impact

...and wants root-cause analysis, regression coverage, or a postmortem write-up. If the user only asks to *fix* a live bug (no retrospective intent), this skill is optional — but offer it once the fix lands.

## Core Execution Rules (non-negotiable)

1. **Input acceptance** — Accept incident logs, outage descriptions, failure reports, production bug postmortem drafts, alert records, and deployment/change records as source material. If a section is unknown, write `Unknown — needs owner input` rather than inventing detail.
2. **Mandatory workflow** — Always run the full 6 stages in order, never skip:
   1. **Symptom freeze** — capture the observed failure exactly as reported (what broke, for whom, when observed), before any theorizing.
   2. **Timeline reconstruction** — order the events: change/trigger → first symptom → detection → mitigation → resolution, with timestamps where available.
   3. **Factor classification** — separate *trigger* (what set it off) from *root cause* (why the system allowed it), plus contributing factors.
   4. **Regression test drafting** — write the test(s) that would have caught this (see rule 4 below).
   5. **Actionable task generation** — convert gaps into owned, dated, verifiable follow-ups (see rule 5).
   6. **Residual risk assessment** — state what remains exposed even after the above land.
3. **Classification constraint** — **Never label human operation error as the root cause.** A person clicking the wrong button, running the wrong command, or mis-typing a value is a *trigger*, not a root cause. The root cause is the **missing system guardrail, missing validation check, flawed config logic, or insufficient test coverage** that let that action cause harm. Always name the systemic gap.
4. **Regression test preference** — match the test tier to the defect:
   - **Cross-module / cross-service failure** → integration or contract test.
   - **Single-module logic defect** → unit test.
   - **Production-environment / deployment / assembly gap** (behaves correctly in isolation but breaks in the real deployment) → end-to-end smoke test.
   Prefer a test that fails against the *pre-fix* code and passes after — state that assertion explicitly.
5. **Action item standardization** — every follow-up action MUST include: **responsible owner**, **deadline**, and **verification method** (how we confirm it is truly done). Use `Owner: TBD` / `Deadline: TBD` only when the user has not supplied it, and flag it for them to fill.

## Fixed Mandatory Output Template (unchangeable)

Output **exactly** these fields, in this order. Do not add, remove, rename, or reorder fields:

```
- Impact:
- Timeline:
- Trigger:
- Root cause:
- Detection gap:
- Mitigation gap:
- Regression test:
- Follow-up actions:
- Residual risk:
```

Field guidance:
- **Impact** — who/what was affected, scope, duration, severity.
- **Timeline** — ordered events with timestamps (freeze → detect → mitigate → resolve).
- **Trigger** — the immediate action or event that set the failure in motion.
- **Root cause** — the systemic gap (guardrail/validation/config/coverage), per rule 3 — never "human error".
- **Detection gap** — why it was not caught earlier (missing alert, blind spot, tests-green-but-broken).
- **Mitigation gap** — why recovery was slow or manual (no rollback, no runbook, no kill switch).
- **Regression test** — the concrete test(s) per rule 4, with tier and the fail-before/pass-after assertion.
- **Follow-up actions** — owned/dated/verifiable items per rule 5.
- **Residual risk** — what stays exposed after everything above ships.

## Invocation

The user pastes raw incident content directly (logs, stack traces, deployment records, user impact). Auto-trigger and return the analysis in the fixed template above.

Example:
```
Postmortem raw incident content:
[outage logs, error stack traces, deployment records, user impact description]
Run Postmortem To Tests skill to generate standardized analysis
```

## Notes for this repository

This project already practises the exact tiering this skill prescribes, so map onto it directly:
- **Assembly/composition-root gaps** (e.g. a middleware silently commented out while the whole suite stays green) → source-code assembly guard (`tests/server-assembly-guard.test.js`) **and** a runtime smoke (`scripts/smokeAssembly.js` / `npm run smoke:assembly`). Per the project's 法则 1.5, both layers are required: source guard proves the code is written; the smoke proves the running service actually applies it.
- **Single-module logic** → Jest unit test under `backend/tests/` (`npx jest --runInBand --forceExit`).
- **Cross-module** → integration/contract test (e.g. supertest against a route).
- Root-cause wording must follow this repo's culture: `改进思考与法则.md` treats "tests green ≠ system healthy" and "judge before executing" as top laws — frame the *systemic* gap, not the operator.
