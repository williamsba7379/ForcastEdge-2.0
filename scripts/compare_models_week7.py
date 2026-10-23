#!/usr/bin/env python3
"""Grade only frozen pre-kickoff NFL winner picks for A/B/C on identical games.
Never backfill picks from post-kickoff automated drafts.
"""
import datetime as dt
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"
def load(name):return json.loads((DATA/name).read_text())
def timestamp(value):return dt.datetime.fromisoformat(value.replace("Z","+00:00"))
def main():
    ab=load("prospective-head-to-head/2026-10-22.json")
    c=load("model-c-week7-2026.json")
    board=load("nfl-scoreboard.json")
    assert ab["season"]==c["season"]==board["season"]["year"]
    assert c["week"]==board["week"]["number"]==7
    c_by_id={str(g["id"]):g for g in c["games"]}
    board_by_id={str(g["id"]):g for g in board["events"]}
    rows=[]
    for game in ab["games"]:
        key=str(game["id"])
        pilot=c_by_id.get(key)
        event=board_by_id.get(key)
        if not pilot:continue
        kickoff=timestamp(game["date"])
        frozen=timestamp(ab["frozenAt"])
        # C has date-only metadata; require creation day to precede game day.
        c_day=dt.date.fromisoformat(c["createdAt"])
        eligible=frozen<kickoff and c_day<kickoff.date()
        if not eligible:continue
        picks={"A":game["baseline30Pick"],"B":game["experimental0Pick"],"C":pilot["pick"]}
        assert all(p in (game["home"],game["away"]) for p in picks.values())
        winner=None
        if event and event.get("status",{}).get("type",{}).get("completed") is True:
            competitors=event.get("competitions",[{}])[0].get("competitors",[])
            winners=[x.get("team",{}).get("displayName") for x in competitors if x.get("winner") is True]
            if len(winners)==1 and winners[0] in (game["home"],game["away"]):
                winner=winners[0]
        rows.append({"id":key,"date":game["date"],"away":game["away"],"home":game["home"],
          "winner":winner,"picks":picks,"conditionalC":bool(pilot.get("conditional")),
          "correct":{model:(pick==winner if winner else None) for model,pick in picks.items()}})
    assert len(rows)==len(ab["games"])==len(c["games"]),"Model matchup coverage differs; refusing misleading comparison"
    summary={}
    for model in ("A","B","C"):
        wins=sum(r["correct"][model] is True for r in rows)
        losses=sum(r["correct"][model] is False for r in rows)
        summary[model]={"wins":wins,"losses":losses,"pending":len(rows)-wins-losses,
          "accuracyPct":round(100*wins/(wins+losses),2) if wins+losses else None}
    output={"season":ab["season"],"week":c["week"],"status":"FROZEN_PREKICKOFF_COMPARISON",
      "models":{"A":"30% recent form","B":"0% recent form","C":"analyst-adjusted Week 7 pilot, NOT automated engine"},
      "frozenABAt":ab["frozenAt"],"pilotCCreatedAt":c["createdAt"],
      "limitations":["Model C has date-only creation metadata, not a precise timestamp.",
       "Model C conditional selections are graded as frozen picks without assuming conditions were met.",
       "Automated Model C Week 8 review draft is excluded; no same-game frozen A/B Week 8 baseline.",
       "No betting results, spread, total, or confidence scores are inferred."],
      "summary":summary,"games":rows}
    target=DATA/"model-comparison-week7-2026.json"
    target.write_text(json.dumps(output,indent=2)+"\n")
    print("Model A/B/C Week 7:",summary)
if __name__=="__main__":main()
