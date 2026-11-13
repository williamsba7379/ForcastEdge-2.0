import unittest
from research.model_c_delivery_outcome_gate import assess

class ModelCDeliveryOutcomeGate(unittest.TestCase):
    def test_run_179_green_job_but_skipped_gate_fails_delivery(self):
        result = assess(scheduled=True, time_gate_run=False, job_conclusion="success",
                        steps={"Commit draft only": "skipped"}, expected_delivery=True)
        self.assertEqual(result["status"], "FAILED_SKIPPED_DELIVERY")
        self.assertFalse(result["delivered"])

    def test_run_180_failed_injury_audit_fails_delivery(self):
        result = assess(scheduled=True, time_gate_run=True, job_conclusion="failure",
                        steps={"Commit draft only": "skipped"}, expected_delivery=True)
        self.assertEqual(result["status"], "FAILED_JOB")
        self.assertFalse(result["delivered"])

    def test_successful_job_without_commit_fails_delivery(self):
        result = assess(scheduled=True, time_gate_run=True, job_conclusion="success",
                        steps={"Commit draft only": "skipped"}, expected_delivery=True)
        self.assertEqual(result["status"], "FAILED_MISSING_REQUIRED_STEP")

    def test_successful_steps_still_need_output_provenance(self):
        steps = {name: "success" for name in (
            "Generate independent Model C review draft",
            "Generate separate Model C-QB experimental shadow",
            "Validate generated Model C review draft", "Commit draft only")}
        result = assess(scheduled=True, time_gate_run=True, job_conclusion="success",
                        steps=steps, expected_delivery=True)
        self.assertEqual(result["status"], "UNVERIFIED_OUTPUT_PROVENANCE")
        self.assertFalse(result["delivered"])

    def test_early_scheduled_check_not_mislabeled_as_delivery(self):
        result = assess(scheduled=True, time_gate_run=False, job_conclusion="success",
                        steps={}, expected_delivery=False)
        self.assertEqual(result["status"], "NOT_A_DELIVERY_ATTEMPT")

if __name__ == "__main__":
    unittest.main()
