#!/usr/bin/env python3
"""Research-only QB impact readiness audit. No prediction changes."""
import json
import pathlib
import datetime as dt

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def audit(history, performance):
    games=history.get("games",[])
    seasons=sorted(set(g.get("season") for g in games if g.get("season") is not None))
    players=performance.get("teams",{})
    player_records=sum(len(team) for team in players.values())
    # Aggregated passing totals lack game-specific starter identity and
    # pregame point-in-time features, so cannot support causal QB change estimates.
    return {
        "status":"RESEARCH_ONLY_NOT_READY_FOR_IMPACT_ESTIMATION",
        "historicalFinalGames":len(games),
        "historicalSeasons":seasons,
        "teamsWithAggregatedPassing":len(players),
        "aggregatedPlayerRecords":player_records,
        "hasHistoricalGameSpecificStarterTimeline":False,
        "hasPregameQBFeaturesForBacktesting":False,
        "canEstimateCalibratedQBPointAdjustment":False,
        "requiredNextDataset":"Historical game-by-game starting QB identities with dated sources and pre-kickoff passing features",
        "methodology":"Time-ordered held-out seasons; compare baseline to QB-feature model on identical games; report MAE, winner accuracy and calibration; no lookahead.",
        "guardrail":"Never apply an adjustment to live Model C or edit frozen picks until out-of-sample validation."
    }

def main():
    report=audit(json.loads((DATA/"nfl-historical-results.json").read_text()),
                 json.loads((DATA/"model-c-qb-performance.json").read_text()))
    report["generatedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
    (DATA/"model-c-qb-impact-readiness.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
