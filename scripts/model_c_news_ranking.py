#!/usr/bin/env python3
"""Prioritize official-team news links for manual review, never starter confirmation."""
import json
import pathlib
import re
import datetime as dt

ROOT=pathlib.Path(__file__).resolve().parents[1]/"data"
MONTHS={m:i for i,m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),1)}

def contains(text,term):
    return bool(term) and re.search(r"(?<![a-z])"+re.escape(term.lower())+r"(?![a-z])",text.lower()) is not None

def rank_link(game,link):
    text=(link.get("headline","")+" "+link["url"].replace("-"," ")).lower()
    reasons=[]
    score=0
    names=[game.get("recentPrimaryPasserCandidate"),game.get("depthChartCandidate")]
    names += [x.get("name") for x in game.get("reportedInjuryFlags",[])]
    if any(contains(text,n) for n in names if n):
        score+=5;reasons.append("PLAYER_NAME")
    if any(contains(text,t) for t in ("quarterback","qb","starter","starting")):
        score+=3;reasons.append("QB_TERMS")
    if any(contains(text,t) for t in ("injury","injured","questionable","practice","inactive","ruled out","named starter")):
        score+=2;reasons.append("STATUS_TERMS")
    if contains(text,game["opponent"]):
        score+=3;reasons.append("OPPONENT")
    match=re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(20\d{2})\b",link.get("headline",""),re.I)
    date=None
    if match:
        try:
            date=dt.date(int(match[3]),MONTHS[match[1].title()],int(match[2]))
            kickoff=dt.datetime.fromisoformat(game["kickoff"].replace("Z","+00:00")).date()
            delta=(kickoff-date).days
            if 0<=delta<=7:score+=3;reasons.append("RECENT_PRE_GAME")
            elif delta<0:score-=15;reasons.append("AFTER_KICKOFF")
            else:score-=10;reasons.append("OLD_NEWS")
        except ValueError:date=None
    if date is None:reasons.append("DATE_UNVERIFIED")
    # Exclude stale and postgame links from the actionable review shortlist.
    eligible=date is not None and 0<=(kickoff-date).days<=7
    if not eligible:reasons.append("NOT_ELIGIBLE_FOR_PREGAME_SHORTLIST")
    return {"url":link["url"],"headline":link.get("headline",""),"score":score,"reasons":reasons,
            "dateFromHeadline":date.isoformat() if date else None,"pregameShortlistEligible":eligible,
            "status":"UNVERIFIED_LINK_FOR_HUMAN_REVIEW"}

def build(discovery,queue):
    teams={t["team"]:t for t in discovery["teams"]}
    items=[]
    for game in queue["items"]:
        source=teams.get(game["team"],{})
        links=[rank_link(game,link) for link in source.get("candidates",[])]
        links.sort(key=lambda x:(not x["pregameShortlistEligible"],-x["score"],x["url"]))
        items.append({"gameId":game["gameId"],"team":game["team"],"opponent":game["opponent"],
                      "fetchStatus":source.get("fetchStatus","MISSING"),"reviewRequired":True,
                      "rankedLinks":links})
    return {"status":"RANKED_LINKS_ONLY_NOT_STARTER_EVIDENCE","season":queue.get("season"),
            "week":queue.get("week"),"automaticConfirmations":0,"items":items}

if __name__=="__main__":
    discovery=json.loads((ROOT/"model-c-official-qb-discovery.json").read_text())
    queue=json.loads((ROOT/"model-c-qb-review-queue.json").read_text())
    output=build(discovery,queue)
    (ROOT/"model-c-qb-ranked-news.json").write_text(json.dumps(output,indent=2)+"\n")
    print("Ranked links for",len(output["items"]),"team-game reviews; no starter confirmations")
