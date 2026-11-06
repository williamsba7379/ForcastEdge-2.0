# NFL A/B full-slate audit (draft PR #5; research-only)

The isolated `scripts/nfl_ab_full_slate_audit.py` validates a complete expected slate against v2 raw ESPN responses, their SHA-256 hashes, game-level hashes, response-to-game links, observed-final times and a fixed historical cutoff. It uses the production `scripts.nfl_team_strength.team_metrics` function and the original A (30% recent differential) and B (0% recent differential) formulas. Identical A/B selections are preserved independently. Any missing game, duplicate ID, insufficient team history, altered evidence, or post-cutoff response fails closed.

The 15-game tests in `tests/test_nfl_ab_full_slate_audit.py` use a *synthetic* future slate and deterministic offline ESPN response fixtures; they do not represent actual upcoming NFL games or archived picks. The module does not generate a frozen card, grade wagers, or write to production.

A November 6 capture cannot replay November 4 Week 9 picks: its retrieval timestamps are after the historical freeze. Historical replay requires a verified immutable capture from before the original cutoff. The existing prospective generator currently fetches latest ESPN results, does not store original input evidence with each frozen card, and supports winner-only experimental A/B. It must not be silently substituted for a verified publisher.

Remaining publication blockers:
1. Confirm hosted full-slate tests and audit real v2 evidence in an isolated job; do not merge on offline fixtures alone.
2. Bind future Wednesday freeze to a verified *at-or-before-cutoff* capture and immutable provenance, including a complete independently verified schedule.
3. Validate per-game A/B selections against their true archived input snapshots. Do not backfill missing Week 9 history.
4. C and C-QB require their own verified QB availability and independent pre-kickoff outputs.
5. Four-model publication must require all four selections for every scheduled game, with traceable source times, explicit NO BET, and no invented scores, spread, total or confidence. Produce a printable report only from a complete verified card.

Do not merge this draft PR or modify frozen picks, NO BET, C/C-QB, existing PRs or production workflows without separately approved validation.

## Wednesday A/B read-only handoff (draft branch only)

`scripts/nfl_ab_wednesday_handoff.py` calls the strict v2 raw-response full-slate audit with a separate, independently supplied schedule. It rejects missing, duplicate or changed IDs, teams, kickoff dates and seasons. Each row contains **both** `picks.A` and `picks.B`, even when equal, with research edges and per-team historical sample sizes. SHA-256 digests bind the input capture and expected schedule. It never creates a freeze, wager, printable report, or production artifact; `publishable=false` and `officialFrozen=false` are explicit.

`tests/test_nfl_ab_wednesday_handoff.py` covers a synthetic 15-game complete slate, determinism, no mutation, cutoff and hash tampering, missing history, schedule mismatch, identical A/B selections, and preservation of disagreement. The disagreement-preservation test uses a mocked *audit result* solely to exercise the adapter mapping; it is not evidence of a real historical disagreement.

Hosted workflow discovery already runs `test_nfl_ab_*.py`, which includes the new adapter tests. A green hosted result is required before treating the isolated branch as validated. A separate independent Wednesday schedule snapshot and an authentic, on-time ESPN capture must be provided for actual games; no retrospective Week 9 backfill is permitted.

C/C-QB still require separately verified QB evidence and frozen pre-kickoff model selections. The four-model publisher must fail closed when either is absent. The present A/B research handoff provides winner-only choices and *does not* supply validated score, spread, total, calibrated confidence or market timestamps; printable output must not invent these.
