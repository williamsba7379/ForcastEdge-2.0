#!/usr/bin/env python3
"""Isolated research audit: new evidence only; no changes to historical or frozen cards."""
import datetime as dt
import hashlib
import json
import os
import pathlib
import urllib.request
from model_c_engine import extract_history, team_form
from nfl_four_model_head_to_head import freeze, stamp

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=ROOT/"research/week9-integrity"
SOURCES=[
 "https://www.nfl.com/schedules/2026/by-week/week-8",
 "https://www.west42sports.com/2026/11/01/nfl-2026-27-weekly-schedule-scores-and-standings/",
]
SCORES=[
 ("Carolina Panthers","Green Bay Packers",19,27),
 ("Baltimore Ravens","Buffalo Bills",10,36),
 ("Tennessee Titans","Cincinnati Bengals",36,43),
 ("Arizona Cardinals","Dallas Cowboys",33,30),
 ("Minnesota Vikings","Detroit Lions",15,19),
 ("Indianapolis Colts","Jacksonville Jaguars",7,42),
 ("Las Vegas Raiders","New York Jets",38,33),
 ("Cleveland Browns","Pittsburgh Steelers",6,27),
 ("Atlanta Falcons","Tampa Bay Buccaneers",0,16),
 ("Los Angeles Chargers","Los Angeles Rams",9,24),
 ("Kansas City Chiefs","Denver Broncos",24,28),
 ("New England Patriots","Miami Dolphins",24,19),
 ("Philadelphia Eagles","Washington Commanders",10,27),
 ("Chicago Bears","Seattle Seahawks",34,17),
]
FROZEN="2026-week-9-refresh-20261104T171826Z.json"

def pick_ab(g,history,now):
    old=extract_history(history,min(now,stamp(g["date"])),2026)
    def diffs(team):
        return [h-a if home==team else a-h for _,away,home,a,h in old if team in (away,home)]
    h=diffs(g["home"]);a=diffs(g["away"])
    def pick(w):
        if min(len(h),len(a))<2:return g["home"]
        hs=(1-w)*sum(h)/len(h)+w*sum(h[-3:])/min(3,len(h))
        aw=(1-w)*sum(a)/len(a)+w*sum(a[-3:])/min(3,len(a))
        return g["home"] if hs-aw+1.5>=0 else g["away"]
    return {"A":pick(.3),"B":pick(0)}

def build_rows(week8):
    lookup={(g["away"],g["home"]):g for g in week8["games"]}
    assert len(lookup)==14 and len(SCORES)==14
    rows=[]
    for away,home,sa,sh in SCORES:
        g=lookup[(away,home)]
        rows.append({"season":2026,"week":8,"id":g["id"],"date":g["date"],
                     "away":away,"home":home,"awayScore":sa,"homeScore":sh,
                     "winner":home if sh>sa else away,"isFinal":True,
                     "finalizationTimestamp":None,"originalRetrievalTimestamp":None,
                     "availabilityAtWeek9Freeze":"UNPROVEN"})
    return rows

def fetch_sources():
    evidence=[]
    for url in SOURCES:
        req=urllib.request.Request(url,headers={"User-Agent":"ForecastEdge-Research-Audit/1.0"})
        with urllib.request.urlopen(req,timeout=25) as response:
            body=response.read(4_000_001)
            if len(body)>4_000_000:raise ValueError("Oversized evidence response")
            if response.status!=200:raise ValueError("Evidence HTTP failure")
            evidence.append({"url":url,"retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
                             "httpStatus":response.status,"sha256RawResponse":hashlib.sha256(body).hexdigest(),
                             "byteCount":len(body),"finalizationTimestamp":None,
                             "historicalRetrievalTimestamp":None})
    return evidence

def audit(history,week8,card,now):
    rows=build_rows(week8)
    original_ids={str(g["id"]) for g in history["games"]}
    if any(str(g["id"]) in original_ids for g in rows):
        raise ValueError("Duplicate historical game")
    baseline=[];replayed=[]
    for g in card["games"]:
        original=pick_ab(g,history,stamp(card["frozenAt"]))
        if any(original[m]!=g["picks"][m] for m in ("A","B")):
            baseline.append({"id":g["id"],"matchup":g["away"]+" @ "+g["home"],
                             "expected":{m:g["picks"][m] for m in ("A","B")},"reproduced":original})
        combined={**history,"games":history["games"]+rows}
        after=pick_ab(g,combined,stamp(card["frozenAt"]))
        replayed.append({"id":g["id"],"matchup":g["away"]+" @ "+g["home"],
                         "frozen":g["picks"],"researchAB":after,
                         "changedAB":[m for m in ("A","B") if after[m]!=g["picks"][m]],
                         "C":"NOT_REPLAYED_WITH_ELIGIBLE_EVIDENCE",
                         "C-QB":"NOT_REPLAYED_WITH_ELIGIBLE_EVIDENCE"})
    return baseline,replayed,rows

def main():
    history=json.loads((DATA/"nfl-historical-results.json").read_text())
    week8=json.loads((DATA/"four-model-head-to-head/2026-week-8.json").read_text())
    card=json.loads((DATA/"four-model-head-to-head"/FROZEN).read_text())
    baseline,replayed,rows=audit(history,week8,card,dt.datetime.now(dt.timezone.utc))
    # Evidence retrieval is current, never backdated. Failure prevents publication.
    sources=fetch_sources()
    snapshot={"type":"RESEARCH_EVIDENCE_NOT_HISTORICAL_AVAILABILITY_PROOF",
      "retrievedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "scoreTranscription":"Cross-checked against NFL and secondary published score listings; manual transcription, not machine-parsed from raw responses",
      "sources":sources,"games":rows,
      "week9FrozenAt":card["frozenAt"],"week9AvailabilityVerified":False,
      "originalFinalizationTimestampsAvailable":False}
    OUT.mkdir(parents=True,exist_ok=True)
    stamp_id=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ev=OUT/("week8-evidence-"+stamp_id+".json")
    with ev.open("x") as f:json.dump(snapshot,f,indent=2)
    report={"status":"RESEARCH_ONLY_NOT_PROMOTION_READY","frozenCard":FROZEN,
            "baselineDiscrepancies":baseline,"replayedGames":replayed,
            "changedGames":sum(bool(g["changedAB"]) for g in replayed),
            "sourceEvidence":ev.name,"missingCAndCQBReplays":True,
            "historicalAvailabilityProven":False}
    with (OUT/("week9-replay-"+stamp_id+".json")).open("x") as f:json.dump(report,f,indent=2)
    print(json.dumps({"evidence":str(ev),"baselineDiscrepancies":baseline,
                      "changedGames":report["changedGames"],"changes":[g for g in replayed if g["changedAB"]],
                      "promotable":False},indent=2))
    if baseline:raise SystemExit("Baseline A/B reproduction mismatch; research replay cannot be promoted")

if __name__=="__main__":main()
