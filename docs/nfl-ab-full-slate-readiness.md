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
