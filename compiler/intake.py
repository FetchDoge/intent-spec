#!/usr/bin/env python3
"""IntentSpec v0.1 intake compiler — Pass 1 Capture + Pass 2 Recover.

Compiles a raw operator utterance into a typed, content-addressed IntentSpec
intermediate representation and immediately exposes pre-execution verification
(structural checks + heuristic intent-diff gate).

One law: The Intent Compiler does not re-decide anything the estate already
decides. Compile to the router, never become a router.

Usage:
    python3 compiler/intake.py "<raw utterance>" [--verify] [--out <path>]
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path to access validator
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validator.validator import (
    CONSTRAINT_HINTS,
    IRREVERSIBLE_VERBS,
    check_drift,
    check_structural,
    words,
)


def extract_explicit_constraints(text: str) -> list[str]:
    """Extract constraint clauses from the raw text based on known constraint hints."""
    text_lower = text.lower()
    if not any(h in text_lower for h in CONSTRAINT_HINTS):
        return []

    # Split text into candidate phrases/clauses by punctuation
    chunks = re.split(r"[;\n.]+", text)
    extracted = []
    for chunk in chunks:
        c_strip = chunk.strip()
        c_lower = c_strip.lower()
        if any(h in c_lower for h in CONSTRAINT_HINTS) and len(c_strip) > 3:
            extracted.append(c_strip)

    if not extracted and any(h in text_lower for h in CONSTRAINT_HINTS):
        extracted.append(text.strip())
    return extracted


def compile_intent(
    utterance: str,
    *,
    timestamp: str = None,
    attachments: list[str] = None,
    references: list[str] = None,
    proposed_deliverable: str = None,
    proposed_lane_brief: str = None,
    authority_override: str = None,
) -> dict:
    """Compile raw operator intent into a canonical IntentSpec dictionary.

    Computes a content-addressed intent_id (SHA-256 :16), captures raw utterance
    verbatim, extracts explicit constraints, and narrows authority to 'ask' tier
    whenever irreversible verbs are detected.
    """
    raw_utterance = (utterance or "").strip()
    if not raw_utterance:
        raise ValueError("Raw utterance cannot be empty.")

    # Content-addressed intent_id: sha256 hex truncated to 16 chars per schema
    intent_id = hashlib.sha256(raw_utterance.encode("utf-8")).hexdigest()[:16]
    ts = timestamp or datetime.now(timezone.utc).isoformat()

    # Pass 2: Recover objective and constraints
    objective = raw_utterance
    explicit_constraints = extract_explicit_constraints(raw_utterance)

    # Authority tier: narrow to 'ask' if any irreversible verbs are present
    utterance_words = set(words(raw_utterance))
    deliverable_words = set(words(proposed_deliverable or ""))
    combined_words = utterance_words | deliverable_words
    found_irreversible = sorted(w for w in combined_words if w in IRREVERSIBLE_VERBS)

    if found_irreversible:
        tier = "ask"
        basis = (
            f"irreversible verbs detected {found_irreversible} — requires operator confirmation ('ask' tier)"
        )
        failure_conditions = [
            "kill / rollback: abort execution and undo changes if unexpected irreversible actions occur"
        ]
    else:
        tier = authority_override if authority_override in ("log", "build-report", "ask") else "build-report"
        basis = "read-only or non-destructive task; build-report tier default"
        failure_conditions = [
            "halt and report failure if objective cannot be satisfied within explicit constraints"
        ]

    deliverable = proposed_deliverable if proposed_deliverable is not None else objective
    lane_brief = proposed_lane_brief if proposed_lane_brief is not None else objective

    epistemics = {
        "objective": "EXPLICIT",
        "authority": "EXPLICIT",
        "scope": "EXPLICIT",
    }
    if explicit_constraints:
        epistemics["constraints"] = "EXPLICIT"

    spec = {
        "intent_id": intent_id,
        "raw": {
            "utterance": raw_utterance,
            "timestamp": ts,
            "attachments": attachments or [],
            "references": references or [],
        },
        "objective": objective,
        "deliverable": deliverable,
        "desired_state": f"Completed: {objective}",
        "authority": {
            "tier": tier,
            "basis": basis,
        },
        "constraints": {
            "explicit": explicit_constraints,
            "inferred": [],
        },
        "scope": {
            "in": [objective],
            "out": [],
        },
        "epistemics": epistemics,
        "lane_brief": lane_brief,
        "unknowns": [],
        "ambiguities": [],
        "success_conditions": [
            "deliverable produced according to explicit constraints",
            "zero unverified irreversible actions",
        ],
        "failure_conditions": failure_conditions,
        "verification": {
            "probes": ["verify deliverable matches objective and constraint checklist"],
            "readback": "operator verifies completed output",
            "regression_checks": [],
        },
        "receipt": {
            "trace": "session tool log",
            "receipt": "output artifacts verified against spec",
            "next": "operator review or lane handoff",
        },
    }
    return spec


def intake_and_verify(utterance: str, **kwargs) -> tuple[dict, list[dict], str]:
    """Compiles the utterance and immediately runs structural and drift checks."""
    spec = compile_intent(utterance, **kwargs)
    structural = check_structural(spec)
    drift = check_drift(spec)
    findings = structural + drift
    errors = [f for f in findings if f.get("severity") == "error"]
    verdict = "FAIL" if (errors or drift) else "PASS"
    return spec, findings, verdict


def main():
    parser = argparse.ArgumentParser(
        description="IntentSpec intake compiler: compile raw operator utterance into a typed IntentSpec."
    )
    parser.add_argument(
        "utterance",
        nargs="?",
        default=None,
        help="Raw natural language utterance (reads from stdin if '-' or omitted)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run structural and intent-diff verification gate on the compiled spec",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Path to write the compiled JSON spec to",
    )
    args = parser.parse_args()

    if not args.utterance or args.utterance == "-":
        if sys.stdin.isatty():
            parser.print_help(sys.stderr)
            sys.exit(2)
        raw_text = sys.stdin.read().strip()
    else:
        raw_text = args.utterance.strip()

    if not raw_text:
        print("error: empty utterance", file=sys.stderr)
        sys.exit(2)

    try:
        if args.verify:
            spec, findings, verdict = intake_and_verify(raw_text)
            output = {
                "intent_id": spec["intent_id"],
                "verdict": verdict,
                "findings": findings,
                "spec": spec,
            }
            formatted = json.dumps(output, indent=2)
            if args.out:
                Path(args.out).write_text(json.dumps(spec, indent=2), encoding="utf-8")
            print(formatted)
            sys.exit(0 if verdict == "PASS" else 1)
        else:
            spec = compile_intent(raw_text)
            formatted = json.dumps(spec, indent=2)
            if args.out:
                Path(args.out).write_text(formatted, encoding="utf-8")
            print(formatted)
            sys.exit(0)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
