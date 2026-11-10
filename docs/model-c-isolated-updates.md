# Model C isolated QB update draft

This is a review-only proposal. It does not install an automation, run a production
workflow, create a real prediction, change any existing grader, or remove NO BET.

## Compatibility and limits

The engine's existing per-game body is extracted into `predict_game`; the weekly
entry point uses the same function and keeps its existing output location. Its
calculation, official-starter validation, adjustment cap, and minimum of ten games
are retained. The new runner validates the **archived full slate** (including its
minimum size) but reproduces and updates only the requested game. It never calls
the weekly `main()` function. Duplicate game IDs also fail validation.

This is a new engine revision. **It cannot be substituted for an older frozen
engine.** An older freeze without this API remains UPDATE BLOCKED. The current
Week 10 missing-baseline problem is not resolved by this PR. No historic freeze
or input archive is created or reconstructed here. A future reviewed freeze must
archive the exact API-capable engine and original inputs alongside its original
prediction before a subsequent QB change can qualify.

QB status alone has no automatic numeric effect in this Model C calculation.
This first draft changes the affected team's official QB declaration only; it
does not accept fresh numeric adjustments or derive points from passer statistics.
All original adjustment inputs remain fixed. Consequently a successful status
update can keep the original winner and model margin unchanged. That is model
behavior, not evidence that the QB change has no football impact. Projected scores,
market spreads, totals and calibrated probabilities are not supplied by this
engine and must not be inferred from its margin or UNVALIDATED confidence label.

## Required reviewed baseline bundle (JSON)

The runner consumes, but does not create or alter, an archived baseline bundle.
Required fields:

| Field | Requirement |
| --- | --- |
| `schemaVersion`, `reviewed` | `1`, `true`; provenance must be checked before marking reviewed |
| `season`, `week` | Same original season and slate |
| `modelVersion` | Exact 40-character engine commit SHA |
| `engineLink` | Repository blob URL at that SHA, ending in `scripts/model_c_engine.py` |
| `engineSha256` | SHA-256 of those exact archived engine file bytes |
| `originalLink` | Immutable repository blob URL at a commit, pointing to the original frozen prediction |
| `inputsLink` | Immutable repository blob URL at a commit, pointing to the actual archived input set |
| `frozenAt`, `modelCGeneratedAt` | Timezone-aware original freeze and generation timestamps |
| `inputsSha256` | SHA-256 of canonical JSON for `inputs`: sorted keys, compact separators, UTF-8, no NaN |
| `original` | Complete original game output from that engine; winner-only cards are insufficient |
| `inputs` | Exactly the objects listed below, as consumed at original generation |

`inputs` contains `selected` (original selected week with its entire `games` array),
`year`, `history_raw`, `adjustments`, `injury_snapshot`, `qb_declarations`,
`qb_stats`, `qb_candidates`, and `depthchart_candidates`. The declarations,
statistics and candidate objects are the inner team maps used by the engine,
not their outer `teams` wrappers. Empty objects are valid only when they faithfully
represent missing inputs at original generation; do not use empty placeholders to
replace unavailable archives.

Reviewed flags and hashes provide auditability, not independent authentication of
an issuer. A human/source-review step must verify the linked original and archived
input provenance. The offline runner does not fetch sources or assert that it has
independently confirmed a report. It checks that the installed engine bytes match
the recorded hash and that the complete original game output reproduces exactly.
It blocks future-dated original QB inputs and history that would activate between
original generation and update time.

## Required reviewed QB event (JSON)

Provide `gameId`, `team`, `quarterback` (the QB identified in the baseline),
`previousStatus`, `newStatus`, `change`, `replacement`, `reviewed: true`,
`officiallyConfirmed: true`, `evidenceKind`, `source`, `evidenceText`, `reportedAt`,
and `declaration`.

| `change` | Allowed `newStatus` | Declaration |
| --- | --- | --- |
| `RULED_OUT` | `OUT` | `CONFIRMED_RULED_OUT`, original QB, no replacement promotion |
| `DOWNGRADED` | `QUESTIONABLE`, `DOUBTFUL`, `OUT` | `CONFIRMED_DOWNGRADED`, original QB, no replacement promotion |
| `CLEARED` | `CLEARED` | `CONFIRMED_STARTER`, same QB, official game-specific team announcement |
| `REPLACED` | `REPLACED` | `CONFIRMED_STARTER`, confirmed replacement, official game-specific team announcement |

`evidenceKind` must be `GAME_STATUS`, `INACTIVE_LIST`, or `STARTER_ANNOUNCEMENT`.
Practice participation and reported expectations are rejected. `source` must be an
HTTPS official NFL/team domain. `reportedAt` must be after the baseline freeze,
at or before the update, and before kickoff. `previousStatus` and `newStatus` must
differ. The declaration must include matching `team`, `gameId`, `source`, `asOf`,
`evidenceText`, `reviewed: true`, `starter`, and `status`. Confirmed starters must
also satisfy the engine's existing `sourceType: TEAM_ANNOUNCEMENT` and seven-day,
pregame source-time checks. A nonconfirmed replacement is not promoted.

This is intentionally conservative: protocol clearance without confirmation that
the player will start cannot be used to fabricate a confirmed-starter declaration.
An unavailable starter and a subsequently confirmed replacement can be separate
substantive updates.

## Manual execution after review, with compatible frozen records

No production workflow is changed. Use an external, dedicated archive:

```sh
mkdir -p /path/outside/repository/model-c-isolated-updates
python scripts/model_c_isolated_update.py \
  --baseline /path/to/archived-baseline-bundle.json \
  --event /path/to/reviewed-official-event.json \
  --output-dir /path/outside/repository/model-c-isolated-updates
```

There is no backdating clock option. The runner rechecks kickoff immediately before
publication and exits 2 with NEEDS REASSESSMENT / UPDATE BLOCKED on failure. It
prints DUPLICATE_SUPPRESSED for the same latest semantic status and prediction
baseline. It rejects stale/conflicting transitions, while allowing a later change
back to a formerly recorded status after an intervening substantive change.

Successful records retain the original and updated complete game outputs, original
links, model SHA/hash, source evidence, exact declaration diff, effective evaluation
time change, NO BET, and `gradingImplemented: false`. A process lock serializes
deduplication; a fully written temporary file is published by exclusive hard link.
No earlier update is overwritten. Archive all successful files durably before the
working environment expires. The runner is not an operating-system sandbox: run
only reviewed repository code with reviewed provenance. The record files are
available for later separate evaluation; **separate grading is not implemented**.

## Verification

```sh
python -m unittest discover -s tests -p 'test_model_c_isolated_update.py' -v
```

Tests use synthetic 2030 fixtures only, including exact weekly-output regression
against the unmodified engine blob `f727e761bd7ab52b5fa6224b29e80d7bf5e68fd9`,
single-game invocation counting, exact baseline replay, input/hash failures,
official-source and practice/expectation rejection, full-slate size/ID checks,
postkickoff refusal, concurrent duplicate suppression, later substantive
transitions, append-only records and preservation of NO BET.
