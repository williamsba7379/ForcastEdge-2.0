# ForecastEdge 2.0 iPhone PWA

This is a functional, offline-capable **dashboard shell**, not a trained sports model or live prediction feed. It displays manually imported JSON reports, pool picks, Monday tiebreaker, qualified wagers, and performance. It does not invent game probabilities, fetch live odds, or produce picks on its own.

## Deploy
Upload all files to a GitHub repository. GitHub Pages requires a supported Pages configuration; private repository Pages availability depends on your account/plan, and a Pages site may be public even if its source repository is private. Do not put secrets or private API keys in this app. In the repository's Settings → Pages, select Deploy from a branch, main, root. Open the resulting HTTPS site in Safari, Share → Add to Home Screen.

## Use
Open Data & Setup → Load DEMO to inspect the layout (all demo teams are fictional). To use real picks, paste or upload a JSON report and tap Load report. The report persists locally in that browser. Import updated reports as needed.

## Format
```json
{"week":"Week 6","mondayTiebreaker":51,"games":[{"date":"2026-10-18","time":"13:00","away":"Away team","home":"Home team","winner":"Home team","winProbability":0.63,"scoreAway":20,"scoreHome":27,"rating":"NO BET","moneyline":"","spread":"","total":"","notes":"","wager":""}],"results":[{"predictedWinner":"Home team","actualWinner":"Home team","predictedTotal":51,"actualTotal":48}]}
```

Confidence values must come from validated analyses, not arbitrary guesses. `EDGE` or `STRONG EDGE` should be supplied only after price verification and calibration. Records are not automatically updated.

## Proposed Wednesday official four-model handoff (NONPRODUCTION ONLY)

Isolated research implementation on `research/nfl-wednesday-official-handoff-isolated`.
The new official-card reader is disabled by default; no production publishing or app behavior is changed.
No GitHub Actions trigger is enabled. Draft and comparison workflows are not official publishers.
Proposed immutable weekly JSON and printable HTML paths: `data/official-four-model/<season>-week-<week>.json` and `.html`; `latest.json` is **not** written.
The proposed validation contract requires independently approved schedule inputs, all A/B/C/C-QB rows, QB and market evidence, actual timestamped SHA-256 provenance, Wednesday 11 AM America/New_York cutoff and fail-closed behavior. NO BET is mandatory.
Actual publication, automatic workflow execution, tests, PR, merge, deployment and any production change require separate authorization.
Historical content verification is unauthorized; PR #15/#16 VM validation remains deferred.

### Correction-pass safeguards (nonproduction, untested)
The workflow remains triggerless, read-only and guarded by a false job condition. The reader remains disabled and rejects all cards even after local hash checks until independent signed-release and schema verification are available. No automatic fetch or production path is enabled.
The JSON contract separates freeze status from delivery status and requires a release-evidence record; these self-declared fields alone are **not proof**. A separately controlled verifier and trusted artifact manifest are mandatory inputs, and no such authority is provisioned by this branch. Never infer historical certification from these records.
Research artifact preparation requires an explicitly configured disposable root, a new direct-child directory and exclusive file creation. It cannot write latest.json. Filesystem checks alone are not a substitute for separately enforced container isolation and cannot guarantee defense against a malicious concurrent actor.
Immutable history and rollback require independent signed/timestamped checkpoints, append-only retention and separate recovery approval; none is implemented or authorized in this isolated scaffold. NO BET remains a research-only restriction, not a production reclassification.
The test definitions are synthetic and have not been executed. No PR, workflow, merge or production activation is authorized.

### Final bounded correction (not executed or certified)
Research canonicalization uses a deliberately restricted ASCII-printable JSON subset: keys sorted, no extra whitespace, finite safe integers and exact half-unit numeric values. This is **not RFC 8785**, and the half-unit restriction is a temporary research constraint that cannot represent normal calibrated confidence values. No production predictions may be rounded or altered to satisfy it. Cross-language known-answer tests are defined but not executed.
The browser filename regex is corrected. The reader stays disabled and rejects all cards without independent signature and full-schema validation.
Schedule approval and release approval require separately supplied verifiers and trusted evidence, but callback functions alone do **not** establish independent privilege, signatures or authenticated timestamps. Approval must occur between freeze and publication. No trusted authority is connected.
Research output uses directory-descriptor-relative no-follow exclusive file creation; this is not a complete protection against concurrent hostile filesystem actors or partial-write recovery. Only a separately authorized, single-writer, isolated container could execute it safely.
Tests now load the checked-in JSON schema and define negative cases; no tests or workflows were run. This scaffold does not implement full JSON Schema validation, durable append-only history, signed checkpoints or production publication. Historical verification and PR #15/#16 VM validation remain deferred.
