"""Research-only Model C delivery outcome gate. No production writes."""
def assess(*, scheduled, time_gate_run, job_conclusion, steps, expected_delivery):
    """A successful GitHub job is not proof of delivered model outputs."""
    if not expected_delivery:
        return {"status": "NOT_A_DELIVERY_ATTEMPT", "delivered": False}
    if not scheduled:
        return {"status": "NOT_SCHEDULED", "delivered": False}
    if not time_gate_run:
        return {"status": "FAILED_SKIPPED_DELIVERY", "delivered": False}
    if job_conclusion != "success":
        return {"status": "FAILED_JOB", "delivered": False}
    required = ("Generate independent Model C review draft",
                "Generate separate Model C-QB experimental shadow",
                "Validate generated Model C review draft", "Commit draft only")
    if any(steps.get(name) != "success" for name in required):
        return {"status": "FAILED_MISSING_REQUIRED_STEP", "delivered": False}
    # Even successful commit step may have had no changes; external file provenance required.
    return {"status": "UNVERIFIED_OUTPUT_PROVENANCE", "delivered": False}
