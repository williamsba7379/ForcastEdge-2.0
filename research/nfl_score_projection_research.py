"""Isolated, uncalibrated score research; never writes predictions or frozen cards."""
import datetime as dt
import json
import pathlib
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MIN_GAMES = 4

def stamp(value):
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if not t.tzinfo:
        raise ValueError("NAIVE_TIMESTAMP")
    return t.astimezone(dt.timezone.utc)

def prior(raw, cutoff, season):
    records = raw.get("games", raw) if isinstance(raw, dict) else raw
    result = []
    for g in records:
        try:
            if int(g["season"]) != season or stamp(g["date"]) >= cutoff:
                continue
            a, h = float(g.get("awayScore", g.get("scoreAway"))), float(g.get("homeScore", g.get("scoreHome")))
            if a < 0 or h < 0 or a != a or h != h:
                continue
            # A historical record with both final scores is not independently source-verified.
            result.append((stamp(g["date"]), str(g["away"]), str(g["home"]), a, h))
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(result)

def stats(rows, team):
    pts = []; diff = []
    for _, away, home, a, h in rows:
        if team == away:
            pts.append(a); diff.append(a-h)
        elif team == home:
            pts.append(h); diff.append(h-a)
    if len(pts) < MIN_GAMES:
        return None
    return {"points": sum(pts)/len(pts), "seasonDiff":sum(diff)/len(diff),
            "recentDiff":sum(diff[-3:])/min(3,len(diff)), "games":len(pts)}

def project(rows, home, away, *, qb_delta=None):
    h, a = stats(rows, home), stats(rows, away)
    if not h or not a:
        return {"status":"INSUFFICIENT_PRIOR_TEAM_GAMES", "models":{}}
    # Mean points scored by both teams is a research-only total hypothesis,
    # not a market line or an independently calibrated total forecast.
    total = h["points"] + a["points"]
    def result(margin):
        return {"projectedHomeScore":round((total+margin)/2,2),
                "projectedAwayScore":round((total-margin)/2,2),
                "projectedMargin":round(margin,2), "projectedTotal":round(total,2),
                "confidence":"UNVALIDATED", "rating":"NO BET"}
    am = .7*(h["seasonDiff"]-a["seasonDiff"])+.3*(h["recentDiff"]-a["recentDiff"])+1.5
    bm = h["seasonDiff"]-a["seasonDiff"]+1.5
    # C baseline equals A absent verified, sourced point adjustments.
    # Never silently substitute an unverified QB delta.
    models = {"A":result(am), "B":result(bm), "C":result(am)}
    if qb_delta is None:
        models["C-QB"]={"status":"QB_ADJUSTMENT_NOT_VERIFIED", "confidence":"UNVALIDATED", "rating":"NO BET"}
    else:
        models["C-QB"]=result(am+qb_delta)
        models["C-QB"]["status"]="HYPOTHETICAL_VERIFIED_DELTA_INPUT_NOT_AUTHENTICATED_HERE"
    return {"status":"RESEARCH_ONLY_NOT_DELIVERABLE", "models":models,
            "priorGames":{"home":h["games"],"away":a["games"]}, "published":False,
            "historicalFreezeVerified":False, "sourceVerified":False}

def walkforward(raw, season, *, min_date=None):
    games = raw.get("games", raw) if isinstance(raw, dict) else raw
    candidates = []
    for g in games:
        try:
            if int(g["season"]) != season: continue
            when = stamp(g["date"])
            if min_date and when < stamp(min_date): continue
            actual_h = float(g.get("homeScore",g.get("scoreHome")))
            actual_a = float(g.get("awayScore",g.get("scoreAway")))
            if min(actual_h,actual_a) < 0: continue
            candidates.append((when,g,actual_h,actual_a))
        except (ValueError,KeyError,TypeError):continue
    errors = {m:{"n":0,"home":0.,"away":0.,"margin":0.,"total":0.} for m in ("A","B","C")}
    for when,g,actual_h,actual_a in sorted(candidates, key=lambda item: (item[0], str(item[1].get("id", "")))):
        rows = prior(raw,when,season)
        prediction = project(rows,g["home"],g["away"])
        if prediction["status"] != "RESEARCH_ONLY_NOT_DELIVERABLE": continue
        for model in errors:
            p=prediction["models"][model];e=errors[model];e["n"]+=1
            for field,delta in (("home",p["projectedHomeScore"]-actual_h),("away",p["projectedAwayScore"]-actual_a),("margin",p["projectedMargin"]-(actual_h-actual_a)),("total",p["projectedTotal"]-(actual_h+actual_a))):
                e[field]+=abs(delta)
    return {"status":"RESEARCH_BACKTEST_ONLY_NOT_VALIDATED", "season":season,
            "metrics":{m:{"graded":e["n"], **{k+"MAE":round(e[k]/e["n"],3) if e["n"] else None for k in ("home","away","margin","total")}} for m,e in errors.items()},
            "C-QB":{"graded":0,"reason":"No independently verified historical QB adjustment snapshots"},
            "published":False, "historicalFreezeVerified":False,
            "limitations":["Historical final scores are not independently provenance verified","No as-of source capture evidence","Research totals uncalibrated","No QB-adjusted backtest"]}

if __name__=="__main__":
    root=pathlib.Path(__file__).resolve().parents[1]
    raw=json.loads((root/"data/nfl-historical-results.json").read_text())
    print(json.dumps(walkforward(raw,2026),indent=2))
