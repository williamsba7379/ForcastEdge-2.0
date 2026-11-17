# Winner, spread and total research evaluation

All three categories have equal standing and separate denominators. This
additive, offline tool never updates forecasts, existing graders or schedules.
It creates a new report with exclusive file creation and refuses overwrites.
No data is fetched. No model gains or wagering edges are asserted.

Run from the repository root:

```sh
python scripts/three_market_evaluation.py --predictions frozen.json --results finals.json --markets markets.json --output new-evaluation.json
```

`--markets` is optional. Missing markets still permit winner accuracy and point
error measurement when original point forecasts exist. Missing finals remain
pending. Empty forecasts fail. JSON arrays or CSV files are supported as native
forecast inputs; result and market inputs use JSON arrays below.

## Original forecast adapters

- NFL: original `FROZEN_PREKICKOFF` or separate `FRESH_PREKICKOFF_SNAPSHOT`
  four-model winner-card JSON. Choose one archive, never combine reruns. Names are the
  identity keys because these archives lack team IDs. No points are inferred
  from winners; the companion research scores are not imported as frozen points.
- CFB: original `predictions_snapshot.csv`. `score_difference` is a rating,
  not a point margin. Companion experimental scores are not A1/A2/A3 forecasts.
- NBA: immutable `FROZEN` / `NO_PREDICTION` prediction JSON, singly or as an array.
  Imports original margin and total; validates feature cutoff against freeze time.
- Each repository sets its own SPORT constant. Models remain independent.

Explicitly archived point forecasts can use the canonical envelope below. A
caller must verify provenance: this tool checks structure, identity and timestamp
consistency; it cannot prove supplied timestamps or final scores are authentic.
Never reconstruct a missing forecast using later results. A CFB experimental
score forecast must use its own model name and actual original archive timestamp.
Never relabel it A1/A2/A3.

```json
{"canonical_predictions":[{
  "game_id":"1", "home_id":"H", "away_id":"A", "model":"original-model-name",
  "start_utc":"2026-10-31T19:00:00Z", "frozen_at_utc":"2026-10-31T16:00:00Z",
  "winner_id":"H", "projected_margin":5, "projected_total":45,
  "wagering_status":"NO_BET"
}]}
```

`projected_margin` is home minus away. Winner, margin and total may individually
be absent/null. Do not fabricate fields missing from the original archive.
Select exactly one forecast stage/run: duplicate game/model pairs fail rather
than silently choosing EARLY or FINAL or combining overlapping reruns.

Final-score input (include overtime in the verified full-game final):

```json
[{"game_id":"1", "home_id":"H", "away_id":"A",
  "start_utc":"2026-10-31T19:00:00Z", "final":true,
  "home_points":27, "away_points":20}]
```

Market input (one explicitly selected bookmaker snapshot per game):

```json
[{"game_id":"1", "home_id":"H", "away_id":"A",
  "start_utc":"2026-10-31T19:00:00Z",
  "captured_at_utc":"2026-10-31T15:30:00Z",
  "source":"https://example.org/odds", "bookmaker":"example",
  "home_spread":-3, "spread_convention":"SIGNED_HOME", "total_points":46}]
```

All examples are synthetic, not actual predictions or odds. Require exact game,
team and start-time matches. A negative home spread means the home team is the
favorite. Never infer the sign from an unsigned line. Duplicate snapshots fail;
the caller must select the intended bookmaker/time before evaluation.

## Interpreting the report

- Winner accuracy measures the archived outright winner, without moneyline ROI.
- Spread direction uses `projected_margin + home_spread`; total direction uses
  `projected_total - total_points`. These are **research comparisons**, not
  original frozen betting selections. No new picks are saved to history.
- Markets must exist by forecast time, before start, with source and bookmaker.
  Default maximum market age is 24 hours relative to forecast time; override
  explicitly using `--max-market-age-hours`. Later or stale lines stay excluded.
- Wins/losses, pushes, no-direction, missing projections/markets, invalid records
  and pending finals are separate. Accuracy excludes pushes and unavailable rows.
- Total-points MAE and margin MAE have separate sample counts and do not require
  market lines. Coverage denominators are supplied prediction rows per model,
  not league schedules; omitted games cannot be detected without a slate manifest.
- All records remain NO_BET. Actionable wagers are zero. Research losses are
  not betting losses. No ROI, price-based edge or calibrated confidence is claimed.

Validation is offline only. The new test workflow cannot write repository data.
Before production scheduling, supply audited final-score/market adapters and
compare reports against verified original archives. Do not merge unrelated NFL
QB or NBA delivery work as part of this change.
