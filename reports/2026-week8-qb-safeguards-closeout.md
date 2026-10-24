# ForecastEdge 2.0 — QB Safeguards Phase Closeout
Date: 2026-10-24

## Scope
End quarterback-specific development for this phase. Return to prospective A/B/C/C-QB full-card NFL winner accuracy testing. Frozen predictions are never rewritten.

## Delivered
- New historical-primary-passer injury triage: scripts/model_c_qb_injury_audit_v2.py.
- Integrated weekly Model C workflow runs v2 and its regression test after draft and QB shadow generation.
- Regression test: tests/test_model_c_qb_injury_audit_v2.py.
- Historical primary passer evidence is research-only and **not proof of official starting status**.
- Model C-QB retains its separate, reviewed, pregame starter and baseline verification requirements before experimental points can change.

## Week 8 snapshot evaluation (14 games; source data from 2026-10-24)
- Four reported QB unavailability alerts.
- P1: Philadelphia Eagles — Jalen Hurts, five earlier primary-passer games; current recent passer Tanner McKee. Escalated as established primary passer absent.
- P2: Cleveland Browns — Dillon Gabriel, zero earlier primary-passer games in the dataset.
- P2: New England Patriots — Behren Morton, zero earlier primary-passer games in the dataset.
- P2: Chicago Bears — Case Keenum, one earlier primary-passer game in the dataset.
- Zero verified QB scoring adjustments. All injury-related score changes remain blocked until reviewed evidence and sufficient passing history are available.

## Validation status and limitations
- Repository input/output structure and the Week 8 classification logic were independently checked against current saved JSON.
- A successful GitHub Actions execution of the new Python script and regression test has **not yet been observed**. Do not represent CI as passing.
- The injury feed itself is not independently confirmed team reporting. The P1 label requires review, not automatic point penalties.
- The historical dataset covers 2026 research primary passers and can miss older established starters or very recent role changes.
- The experimental 0.35 points per adjusted yards per attempt factor is uncalibrated and remains shadow-only.
- Frozen Week 8 four-model snapshot remains at data/four-model-head-to-head/2026-week-8.json.

## Phase decision
Freeze routine QB feature development. Continue the four-model head-to-head competition with independent pregame frozen picks and separate accuracy grading. Reopen QB work only for a demonstrated severe error, broken CI, or measured improvement opportunity.
