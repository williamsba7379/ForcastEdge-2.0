# Proposed NFL Wednesday pre-delivery provenance gate (DESIGN ONLY)

Status: **DRAFT / NOT IMPLEMENTED / NOT APPROVED FOR PRODUCTION**.

Dependency: draft PR #6 (commit e81ccee600c14dae6efcc57baf8217ac77180319), whose 32 hosted offline tests passed. This branch starts from main and does not include PR #6's code. Do not merge either PR implicitly.

## Intended integration boundary

A separately approved future implementation inserts a **read-only validation job** after independent current-week schedule capture and Model C/C-QB evidence generation, but **before any frozen-card publication, grading or commits**. The existing Wednesday workflow currently selects data/model-c-automated-draft.json and data/model-c-qb-shadow.json without requiring both to originate from the same independently verified run. The current four-model workflow can grade an older archive without proving current-week readiness.

The validator must accept explicitly identified **immutable input artifacts**, never glob('latest'), filename sorting, default mutable files, or an automatically selected fallback. Production workflows and existing historical cards remain untouched by this design PR.

## Required inputs (immutable provenance manifest)

- requested NFL season, week, timezone-aware Wednesday 11:00 AM America/New_York cutoff and exact expected game IDs
- separately sourced and timestamped official NFL schedule and ESPN schedule; independent source identities, retrieval timestamps, SHA-256 digests, and normalized game ID/team/kickoff mapping
- immutable Model C draft and C-QB shadow: run ID, commit SHA, artifact ID, SHA-256, generation and retrieval times, season/week, 15-game coverage, and same-run or explicitly linked lineage
- immutable A/B baseline inputs, source lineage and cutoff timestamps
- exact proposed four-model card: immutable bytes and SHA-256; 15 unique IDs and four winner-only picks per game; distinguish winner-only from spreads/totals
- source manifest schema version, workflow identity, producer and trusted evidence source; source identities must be independently checked against the GitHub API, not merely asserted in a user-supplied manifest
- explicit mode (research-only or production candidate); a research-only artifact cannot satisfy production-readiness

## Fail-closed rules

1. Verify request season/week and every fixture ID, home/away identity, and UTC kickoff across both independently captured schedules. Missing, ambiguous, duplicated, conflicting or post-cutoff schedule evidence => NOT_READY.
2. Verify every artifact is retrievable by immutable run/artifact ID and its raw bytes hash matches the manifest; verify GitHub run commit and completed-success status. Missing, stale, mutable or mismatched evidence => NOT_READY.
3. Require pre-cutoff evidence timestamps for every prediction-affecting input, generation before earliest kickoff, and explicit cutoff policy for late information. An after-cutoff research refresh must never be relabeled the 11 AM freeze.
4. Require C and C-QB game parity, no fabricated QB verification, all 15 games, four model winner picks, and explicit NO BET preservation. A/B/C/C-QB provenance must be linked to the same requested slate.
5. Require independently audited production candidate status; PR #6's November 4 isolated snapshot is READ_ONLY_NO_FREEZE and **must always fail production-ready certification**, even though it passes research replay.
6. On any failure emit structured NOT_READY with reason codes and source references; exit nonzero before delivery, artifact promotion, grading or git commit. Do not mutate frozen cards, NO BET, standings or model outputs.

## Outputs

A JSON report with `status: VERIFIED_RESEARCH_ONLY | NOT_READY | VERIFIED_PRODUCTION_CANDIDATE`, `productionReady`, `reasonCodes`, season/week, verified source IDs, digest, cutoff proof and completeness counts. Only an independently approved production path may interpret VERIFIED_PRODUCTION_CANDIDATE. The gate itself never publishes, freezes, grades, sends notifications, modifies data or sets a schedule.

## Rollout and approval (not authorized by this PR)

1. Approve research-only PR #6 separately if desired; do not treat its merge as production activation.
2. In a **separate future implementation PR**, add parameterized validator and offline test fixtures, then a read-only shadow job (permissions: contents: read) using archived Week 8 and Week 9 inputs.
3. Demonstrate valid current-week acceptance; stale Week 8 rejection; missing C/QB artifact rejection; schedule mismatch rejection; post-cutoff source rejection; wrong digest rejection; source-identity spoof rejection; and research-only refusal of production certification.
4. Obtain explicit approval to place the validator as a blocking dependency before any delivery step. Keep the existing production workflow untouched until that approval.
5. Separately validate delivery/notification failure handling; never silently fall back to last week's picks.

## Non-goals

No automatic publication, production workflow modifications, scheduled runs, new picks, backfills, grading, QB declarations, changes to NO BET, historical records, or merges.
