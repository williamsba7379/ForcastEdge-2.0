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
