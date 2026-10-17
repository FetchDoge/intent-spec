# IntentSpec v0.1

**Compiles raw operator intent into a typed IR for existing agent machinery. The validator rejects specs that drift from what the operator said.**

[![Claims integrity](https://github.com/FetchDoge/intent-spec/actions/workflows/claims.yml/badge.svg)](https://github.com/FetchDoge/intent-spec/actions/workflows/claims.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](.github/workflows/claims.yml)

> **Status:** a specification with a working validator and three worked examples. There is no live-estate binding, and nothing here has run in production. See [Status](#status).

**The one law:** the Intent Compiler does not re-decide anything the estate
already decides. It has exactly one output of consequence: a typed
`IntentSpec` that compiles *to* the machinery already running — router,
authority tiers, review lanes, handoff record, receipt. Compile to the
router. Never become a router.

## Architecture

The compiler and validator sit strictly between raw human intent and existing estate machinery — enforcing structural schema rules and catching drift before execution begins:

```mermaid
flowchart TD
    subgraph S1 ["1. Raw Operator Intent"]
        A["Natural language utterance: task, context, instructions"]
    end

    subgraph S2 ["2. Intent Spec Validation"]
        B["Structural checks: schema fields, required vocabularies"]
        C["Intent-diff gate: heuristic drift and escalation detection"]
        B --> C
    end

    subgraph S3 ["3. Compiled IR"]
        D["IntentSpec: typed contract (objective, explicit vs. inferred constraints, scope, authority, epistemics)"]
    end

    subgraph S4 ["4. Target Agent Machinery"]
        E["Router (advisory lane assignment)"]
        F["Authority tiers (log / build-report / ask)"]
        G["Review lanes (conductor, adversary, builder)"]
        H["Handoff records and outcome receipts"]
    end

    A --> B
    C -->|PASS: exit 0| D
    C -.->|FAIL: exit 1| R["Compilation halted (drift or malformed spec rejected)"]
    D --> E
    D --> F
    D --> G
    D --> H
```

## What it guarantees

- **One output of consequence: a typed spec.** The IR is defined in `intent_spec.schema.json` (JSON Schema draft-07). The dependency-free validator does not load the schema file. It re-implements the structural checks in Python.
- **Structural checks reject malformed specs.** They cover required fields, the epistemics/ambiguity/authority vocabularies, and disclosure of inferences.
- **The exit code is the verdict.** `validator/validator.py` exits 0 on PASS, 1 on FAIL, and 2 on bad usage.
- **Routing stays advisory.** The schema makes `route.reason` a string justification, never a score.

The intent-diff gate is **heuristic**, and labeled as such in its output. It flags invented requirements, authority escalation, unmarked irreversible moves, constraint loss, scope expansion and assumption promotion by keyword and stem matching. It measures the shape of drift, not its meaning, so a human reads the diff before any consequential execution.

## Quickstart

```bash
git clone https://github.com/FetchDoge/intent-spec && cd intent-spec
python3 compiler/intake.py "Organize files; do not touch git history" --verify  # PASS (exit 0)
python3 validator/validator.py examples/01-organize-estate.json  # PASS (exit 0)
python3 validator/validator.py examples/02-chat-with-hermes.json  # PASS (exit 0)
python3 validator/validator.py examples/03-drift-caught.json      # FAIL (exit 1)
```

Dependency-free Python 3.

## How it fails

| Condition | Behaviour |
|---|---|
| Missing field or out-of-vocabulary value | Structural finding, verdict FAIL, exit 1 |
| Irreversible verb (e.g. `publish`, `send`) under authority tier `log` | `AUTHORITY_ESCALATION (HEURISTIC)`: irreversible moves require the `ask` tier |
| Irreversible move with no rollback/kill language | `UNMARKED_IRREVERSIBLE (HEURISTIC)` |
| Deliverable words not grounded in the raw utterance | `INVENTED_REQUIREMENTS (HEURISTIC)`, with stem-tolerant matching so paraphrase passes |
| Wrong arguments | Exit 2 |
| Drift the keywords can't see | Not caught. The gate is heuristic, which is why a human reads the diff |

## Evidence

- Examples 01 and 02 return PASS (exit 0).
- Example 03 returns FAIL (exit 1) with four drift findings: `INVENTED_REQUIREMENTS`, `AUTHORITY_ESCALATION`, `UNMARKED_IRREVERSIBLE` and `SCOPE_EXPANSION`.
- 10 unit tests pass: `python3 -m unittest discover tests`.
- `python3 scripts/check_claims.py` passes. CI runs the same check on every push. It verifies README paths, links and secret-shaped strings, not prose truth.

## Contents

- `SPEC.md` — the full specification, headed by the Heilmeier catechism
  (8 questions: what, why now, risks first, cost/clock, milestones with kill
  lines, falsifier)
- `intent_spec.schema.json` — the IR schema (JSON Schema draft-07)
- `validator/validator.py` — structural checks + the intent-diff gate
- `compiler/intake.py` — Pass 1 Capture + Recover intake compiler and pre-execution gate
- `examples/` — three worked `IntentSpec` instances with a provenance note
- `tests/` — unit tests for the validator and intake compiler
- `ADVERSARIAL-REVIEW.md` — the spec's own four council questions, answered
  as kill-attempts, with the two fixes they forced

## Revision history

- **Corrected during build:** the drift gate's first run false-flagged
  paraphrase ("sorted" vs "sort") as invented requirements. Fixed with
  stem-tolerant grounding rather than weakening the check.
- **Corrected after adversarial review:** the "superset of handoff" claim
  failed field-by-field on the id — `intent_id` (content-addressed on the
  utterance) and the handoff id (ledger sequence) are different truths.
  Fixed with an optional `receipt.handoff_id` and an explicit one-join
  mapping rule. The advisory-only routing rule and the no-scores rule
  (`route.reason` is a string justification, never a number) were written
  into the schema.

Corrections are the credential: what changed is recorded here, not hidden.

## Status

- **Designed:** the IR schema, the six compilation passes, the intent-diff
  gate, the validator, the adversarial review.
- **Exercised:** three worked examples in `examples/` — two pass, one
  deliberately fails with four named drift signatures.
- **Not done:** no live-estate binding yet. The milestone that promotes this
  from document to artifact is an estate intake rule — *no spec, no route* —
  which is not built here. Nothing in this repo has run in production.

Built by Marcus Richards, directing AI coding agents.

## License

MIT. See `LICENSE`. Every claim in this README is meant to be checkable by someone who doesn't trust it yet. If something doesn't reproduce on a clean clone, please open an issue.
