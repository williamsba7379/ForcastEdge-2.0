# Draft-only NFL real-artifact shadow verifier

This PR is **research-only** and has no production activation, freezing, publication, grading or GitHub write operations. It does not include or merge draft PR #6 or #7.

The isolated verifier in `research/nfl_real_artifact_shadow.py` accepts an explicitly specified current-week slate and C/C-QB artifact IDs. It retrieves the run and artifact metadata through a read-only GitHub API callback, requires successful producer status, exact run commit/workflow path, non-expired artifact linked to run, then extracts a named ZIP member and checks SHA-256 of raw payload bytes. It verifies game IDs, teams, UTC kickoffs, season/week and Wednesday 11 AM New York cutoff. Every outcome has `productionReady: false`.

**Evidence limits / next blockers:** Hosted tests currently mock GitHub responses; no live GitHub artifact download or real independent NFL schedule source has been exercised. The schedule inputs' source identifiers are supplied by the caller and are not yet authenticated against source HTTP response or retrieval time. The current verifier checks Model C/C-QB, not A/B lineage, QB1 source freshness, market quote lineage, or complete per-input timestamp coverage. The ZIP API transport, redirect destination, payload size, and JSON schema need additional hardening. Do not claim the Week 9 PR #6 archive is a certified Wednesday production freeze; its mode is research-only.

Future work requires separate explicit approval for live read-only shadow capture, independently authenticated NFL/ESPN schedule captures and immutable artifact manifest replay, followed by separate production-integration approval. No automatic publishing, no schedule triggers, no production writes.
