# Week 9 isolated historical-repair approval audit (research only)

**Decision: DO NOT PROMOTE.** Frozen Week 8/9 picks, production history, main, NO BET and QB PRs must remain unchanged.

## Evidence and reproducibility
- Archived Week 8 final-score report: commit `29ec2e1516a4e625717d2fc929c351ae8a07b65a`, Git blob `1f545aa950e8e36ab8d80bbf0a194deace631b92`. Fourteen distinct ESPN-attributed final scores were committed before Week 9 freeze. The original ESPN HTTP retrieval timestamps, original response hashes, and observed-final timestamps were not preserved.
- Original history canonical JSON SHA-256: `8b70ff10c7c7b88defde243d8c57ac920533e73213f437b0dff130ba06b90753`.
- Candidate in-memory history canonical JSON SHA-256: `3fe2ca876ee30ff576eaef3518cd84e6ff4c714b8de1a42ab40656fb060487cb`.
- Candidate adds 14 results, leaves existing records unchanged, and can be rolled back by discarding the candidate. These hashes describe canonical JSON serialization, **not** byte-for-byte hashes of the original file.
- Hosted candidate run `41893166948`: 12/12 fixtures, 14 appended games, zero validation errors, no tracked files modified.
- Hosted controlled comparison `41893557452`: 7/7 fixtures, 15/15 frozen games, zero baseline mismatches, 2 changed games / 7 model-level winner changes, no tracked files modified. Earlier run `41893489710` failed only due to a Python import path; fixed in `aa0acb59291f65171532e138787b927e3195dde5`.

## Production arithmetic versus research implementation
1. `scripts/model_c_engine.py:31-46`: `extract_history` filters season and dates strictly before the earlier of freeze/target kickoff; `team_form` calculates 70% season scoring differential + 30% last-three scoring differential.
2. `scripts/model_c_engine.py:145-159`: Model C computes `base=(home or 0)-(away or 0)+1.5`, applies only explicit verified adjustment inputs, and **rounds margin to two decimals before choosing the winner**. The research replay mirrors this rounding. Model C's source permits optional adjustments, so research is conditional on the checked zero-adjustment inputs.
3. `scripts/nfl_four_model_head_to_head.py:35-45`: A/B each use home/away scoring differential, a +1.5 home edge, and minimum two prior games per team. A weights the most recent three 30%; B uses 0%. Research `scripts/nfl_week9_integrity_research.py:47-60` mirrors the formula; `scripts/nfl_week9_controlled_comparison.py:25-36` fails closed if baseline differs from any frozen pick.
4. `scripts/nfl_four_model_head_to_head.py:15-34,45-55`: C is sourced from an existing Model C draft and C-QB from a separate experimental shadow, not from the A/B function. The freeze requires identical games, pre-kickoff draft timestamps and sourced experimental QB adjustments.
5. `scripts/model_c_engine.py:97-120`: official starter confirmation requires reviewed game-specific official team announcement with bounded pre-kickoff evidence. `scripts/model_c_qb_shadow.py:37-79` additionally requires an independently documented baseline starter and at least 80 pregame passing attempts for both players; experimental points = 0.35 times AYA difference, capped at +/-3 per team. These source-level safeguards are **not independently re-executed** by the controlled comparison.
6. `scripts/nfl_week9_controlled_comparison.py:10-39`: fails closed on starter declarations, nonzero frozen QB edges and nonempty verified adjustment feed. The research C-QB column is a conditional zero-adjustment shadow, not independent QB validation.

## Seven conditional changes
| Matchup | Model | Frozen | Conditional |
|---|---|---|---|
| Cleveland Browns @ New Orleans Saints | A | Cleveland | New Orleans |
| Cleveland Browns @ New Orleans Saints | B | Cleveland | New Orleans |
| Cleveland Browns @ New Orleans Saints | C | Cleveland | New Orleans |
| Cleveland Browns @ New Orleans Saints | C-QB (conditional shadow) | Cleveland | New Orleans |
| Buffalo Bills @ Minnesota Vikings | A | Minnesota | Buffalo |
| Buffalo Bills @ Minnesota Vikings | C | Minnesota | Buffalo |
| Buffalo Bills @ Minnesota Vikings | C-QB (conditional shadow) | Minnesota | Buffalo |

Model B remains Minnesota for Buffalo @ Minnesota. All other 13 games remain unchanged.

## Remaining risks and approval gates
- Original ESPN HTTP capture and finalization timestamps were not archived. Git commit time proves repository availability of results before freeze, not original API observation time.
- Historical source file is stale relative to independently archived Week 8 finals; production data synchronization has not been repaired.
- C-QB shadow is not an independently validated QB-specific replay; source freshness, official confirmation, injury evidence and lineup conflicts still require separate safeguards.
- The candidate replay proves sensitivity to historical inputs, **not** superior prediction accuracy. No future outcomes were used to choose a winner here, but research must not replace pregame frozen picks.
- Before any production promotion: independently verify source hashes and data lineage, add fail-closed historical synchronization with an approved rollback, validate full QB shadow behavior, and obtain explicit approval for a separately reviewed change. Do not overwrite frozen Week 8/9 cards.

**Research disposition:** candidate arithmetic and historical consistency validated; production promotion **BLOCKED**.
