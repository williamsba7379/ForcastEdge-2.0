# Prospective Model C frozen-input capture draft

This proposal depends on draft PR #10's isolated API. It adds a manual prospective
generation/capture path and a separate reviewed-baseline builder. It changes no
production workflow, scheduler, existing forecast, history, grader, Model A/B,
C-QB or NO BET designation. No real capture or prediction is produced by preparing
this draft. Nothing is automatically enabled after review.

## What it preserves

At the moment a **new** review generation is calculated, `capture` preserves:

| Artifact | Contents |
| --- | --- |
| `engine.py` | Exact engine bytes read from the specified Git commit, checked against the installed engine |
| `raw/*.json` | Exact bytes of each present schedule, history, adjustment, injury, starter, performance, candidate and depth-chart input |
| `manifest.json` | Engine commit/hash, per-file hashes, present/missing input inventory, generation/capture times, capture ID, and unreviewed status |
| `inputs.json` | Exact normalized objects passed to `predict_game`, including the original full slate and all original QB assumptions |
| `generation.json` | Complete original per-game outputs, with generation time and review-only/NO BET labels |

Missing optional inputs are recorded as absent, with the same defaults used by the
engine. They are not reconstructed or silently substituted later. Missing schedule,
invalid JSON, a changed engine, an undersized slate, future-dated QB sources,
future results, or a source that changes during calculation causes capture to fail.

The source input objects actually used for calculation come from the bytes stored
in this capture. Source files are reread only to detect concurrent changes; a new
feed is never substituted during calculation. The engine is compiled directly from
the same pinned bytes, without writing an engine bytecode cache.

`capture` generates an independently identified **prospective review draft**. It
cannot attach newly collected inputs to an older production generation. A future
approved freeze process must explicitly use the captured generation as its Model C
source. This PR does not connect the existing freeze workflow to the new path.

## Manual capture, after review and separate operational authorization

Linux with Python 3.9+ and `git` is required. The same checkout must contain the
specified engine commit locally and have exactly those engine bytes installed.
Output directories must exist outside the repository. Review and retain captures
in durable storage; this script does not upload or commit artifacts.

```sh
mkdir -p /external/model-c-frozen-captures
PYTHONDONTWRITEBYTECODE=1 python scripts/model_c_frozen_capture.py capture \
  --repository /path/to/ForcastEdge-2.0 \
  --model-version EXACT_40_CHARACTER_ENGINE_COMMIT \
  --data-dir /path/to/ForcastEdge-2.0/data \
  --output-root /external/model-c-frozen-captures
```

The result is a new content-addressed directory labeled
`UNREVIEWED_PROSPECTIVE_CAPTURE`, with `reviewed: false`. It does **not** declare an
official freeze, source clearance, validated confidence, bet or completed QB rerun.
The normal weekly `main()` and its shared draft output are never called. All games
in this original generation must still be ahead when capture is published.

## Bind to an authentic freeze before creating a baseline

An approved reviewer must first verify the captured generation and the actual
freeze's provenance. The generation must be archived without edits at a permanent
Git commit, including every byte in its directory. The existing prekickoff frozen
card must identify that generation by timestamp and record the same game IDs,
matchups, kickoff strings and Model C winners. Archiving and freezing are outside
this command: it makes no commits, pushes, merges or workflow changes.

```sh
mkdir -p /external/model-c-baseline-bundles
PYTHONDONTWRITEBYTECODE=1 python scripts/model_c_frozen_capture.py bundle \
  --repository /path/to/ForcastEdge-2.0 \
  --capture-dir /external/model-c-frozen-captures/CAPTURE_ID \
  --archive-commit EXACT_40_CHARACTER_ARCHIVE_COMMIT \
  --archive-path path/to/unchanged/CAPTURE_ID \
  --freeze-link https://github.com/williamsba7379/ForcastEdge-2.0/blob/FREEZE_COMMIT/path/to/frozen.json \
  --game-id EXACT_GAME_ID \
  --reviewed \
  --output-dir /external/model-c-baseline-bundles
```

`--reviewed` is an explicit attestation, not automated proof that a person reviewed
the source. The command independently checks every linked archive byte against
the local commit object using `git show`, verifies raw and normalized input consistency, and binds the target
to the pinned engine and frozen card. It also reproduces **only the requested
original game**, at its original generation time, and requires exact equality of
all output fields. It never regenerates the rest of the slate during bundling.
The reviewer must separately confirm that these commits have actually been
published to the named ForecastEdge repository and that their links are accessible;
local object checks do not prove remote publication or source authorship.

The frozen card may have status `FROZEN_PREKICKOFF` or
`FRESH_PREKICKOFF_SNAPSHOT`. It must expose `season`, `week`, `frozenAt`,
`modelCGeneratedAt`, and `games` with `id`, `date`, `away`, `home`, and `picks.C`.
Capture must have finished before the original freeze. All original picks must
have been frozen before their respective kickoffs; the requested game must still
be ahead when its reviewed bundle is published. There is no backdating CLI option.

The result is a distinct `REVIEWED_BASELINE_BUNDLE` compatible with PR #10. It
contains immutable links to the frozen card, full generation, normalized inputs,
and capture manifest, plus the exact original game output and version/hash.
Winner-only cards by themselves remain insufficient; the full earlier capture
must actually exist. No old prediction or capture is relabeled or overwritten.

## Publication and failure behavior

Capture directories are staged completely, checked and flushed, then published
with Linux atomic no-replace rename. Even an existing empty destination is never
replaced. Reviewed bundles are written completely and published by exclusive hard
link; rerunning an identical publication refuses to overwrite. Existing output
records remain untouched. Kickoff is checked again immediately before publication.
Missing inputs, provenance mismatches or other failures print `CAPTURE BLOCKED`
and exit 2. A failed publication never creates a partial visible capture/bundle.

Hashes detect changes; they are not signatures proving who created an artifact.
Review of trusted code, source facts and Git provenance remains required. Run only
trusted reviewed engine commits. Linux filesystem primitives and directory fsync
are required; this proposal does not silently fall back to unsafe replacement.

## What remains blocked

This code cannot repair an older freeze that never archived its original inputs.
It cannot substitute this refactored engine for an older frozen model version.
Live updates still need new verified official QB evidence and PR #10's full checks.
Existing target-side numeric adjustments still block pending dependent-input
reassessment; capture does not invent replacement point adjustments. Separate
grading, automated provenance review, durable uploading and production freeze
integration are **not implemented**.

## Tests

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_model_c_*.py' -v
```

14 new tests use disposable local Git repositories and synthetic 2030 games. They
cover exact raw bytes and optional-file absence, pinned-engine checks, changing
sources, tampering, immutable archive mismatches, mismatched/fabricated freezes,
review attestation, started-game and publication guards, symlinks, minimum slate,
no-overwrite directories/bundles, and capture → authentic fixture freeze → baseline
bundle → isolated affected-game update. Together with PR #10, 33 tests pass.

No real NFL prediction is generated, changed, graded or presented by these tests.
