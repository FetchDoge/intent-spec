"""Tests for the IntentSpec compiler / intake module (Pass 1 Capture + Recover)."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Import validator
spec_val = importlib.util.spec_from_file_location(
    "validator", ROOT / "validator" / "validator.py"
)
validator = importlib.util.module_from_spec(spec_val)
spec_val.loader.exec_module(validator)

# Import compiler/intake
spec_intake = importlib.util.spec_from_file_location(
    "intake", ROOT / "compiler" / "intake.py"
)
intake = importlib.util.module_from_spec(spec_intake)
spec_intake.loader.exec_module(intake)


class TestIntakeCompiler(unittest.TestCase):
    def test_content_addressed_intent_id(self):
        utterance = "Organize my workspace files."
        spec1 = intake.compile_intent(utterance)
        spec2 = intake.compile_intent(utterance)
        self.assertEqual(len(spec1["intent_id"]), 16)
        self.assertEqual(spec1["intent_id"], spec2["intent_id"])

        spec3 = intake.compile_intent("Completely different request.")
        self.assertNotEqual(spec1["intent_id"], spec3["intent_id"])

    def test_raw_utterance_preserved_verbatim(self):
        utterance = "Sort through candidate files and do not touch git history."
        spec = intake.compile_intent(utterance)
        self.assertEqual(spec["raw"]["utterance"], utterance)
        self.assertIn("timestamp", spec["raw"])

    def test_explicit_constraints_extracted(self):
        utterance = "Audit the codebase and do not modify source files; never push commits."
        spec = intake.compile_intent(utterance)
        self.assertGreater(len(spec["constraints"]["explicit"]), 0)
        self.assertEqual(spec["epistemics"]["constraints"], "EXPLICIT")
        # Validator drift check should not flag CONSTRAINT_LOSS
        drift = validator.check_drift(spec)
        codes = [f["code"] for f in drift]
        self.assertNotIn("CONSTRAINT_LOSS (HEURISTIC)", codes)

    def test_irreversible_verbs_narrow_authority_to_ask(self):
        utterance = "Deploy the new container and delete obsolete caches."
        spec = intake.compile_intent(utterance)
        self.assertEqual(spec["authority"]["tier"], "ask")
        self.assertTrue(any("rollback" in fc.lower() or "kill" in fc.lower() for fc in spec["failure_conditions"]))
        # Validator should not flag AUTHORITY_ESCALATION or UNMARKED_IRREVERSIBLE
        drift = validator.check_drift(spec)
        codes = [f["code"] for f in drift]
        self.assertNotIn("AUTHORITY_ESCALATION (HEURISTIC)", codes)
        self.assertNotIn("UNMARKED_IRREVERSIBLE (HEURISTIC)", codes)

    def test_intake_and_verify_clean_pass(self):
        utterance = "Sort and catalog the workspace directory."
        compiled, findings, verdict = intake.intake_and_verify(utterance)
        self.assertEqual(verdict, "PASS")
        self.assertEqual(len(findings), 0)
        # Check against validator's structural check
        structural = validator.check_structural(compiled)
        errors = [f for f in structural if f["severity"] == "error"]
        self.assertEqual(errors, [])

    def test_negative_control_ungrounded_deliverable_fails_gate(self):
        utterance = "Sort the workspace directory."
        # Inject ungrounded deliverable words
        spec = intake.compile_intent(utterance, proposed_deliverable="launch nuclear rocket to Mars orbit")
        structural = validator.check_structural(spec)
        drift = validator.check_drift(spec)
        codes = [f["code"] for f in drift]
        self.assertIn("INVENTED_REQUIREMENTS (HEURISTIC)", codes)
        verdict = "FAIL" if (structural or drift) else "PASS"
        self.assertEqual(verdict, "FAIL")


if __name__ == "__main__":
    unittest.main()
