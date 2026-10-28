#!/usr/bin/env python3
"""Create a new, timestamped four-model card from current pregame inputs.
Never change an earlier frozen card or represent stale inputs as refreshed.
"""
import datetime as dt
import json
from pathlib import Path
from nfl_four_model_head_to_head import DATA,OUT,freeze,stamp

MAX_AGE_HOURS=8
def main():
    draft=json.loads((DATA/"model-c-automated-draft.json").read_text())
    shadow=json.loads((DATA/"model-c-qb-shadow.json").read_text())
    history=json.loads((DATA/"nfl-historical-results.json").read_text())
    now=dt.datetime.now(dt.timezone.utc)
    for label,obj in (("C",draft),("C-QB",shadow)):
        age=(now-stamp(obj["generatedAt"])).total_seconds()/3600
        if age<0 or age>MAX_AGE_HOURS:
            raise ValueError(label+" input is stale ("+str(round(age,1))+" hours); refusing fresh label")
    card=freeze(draft,shadow,history,now)
    card["status"]="FRESH_PREKICKOFF_SNAPSHOT"
    card["inputFreshnessHours"]={k:round((now-stamp(v["generatedAt"])).total_seconds()/3600,2)
                                  for k,v in (("C",draft),("C-QB",shadow))}
    card["note"]="A/B recomputed from latest completed-game history; C and C-QB taken from current independently generated draft/shadow. Historical frozen cards unchanged."
    original=OUT/(str(draft["season"])+"-week-"+str(draft["week"])+".json")
    if original.exists():
        prior=json.loads(original.read_text())
        byid={str(g["id"]):g for g in prior["games"]}
        card["changesFromOriginal"]=[
            {"gameId":g["id"],"changedModels":[m for m,p in g["picks"].items()
              if p!=byid.get(g["id"],{}).get("picks",{}).get(m)]}
            for g in card["games"] if g["id"] in byid and any(
                p!=byid[g["id"]]["picks"].get(m) for m,p in g["picks"].items())]
    filename=str(draft["season"])+"-week-"+str(draft["week"])+"-refresh-"+now.strftime("%Y%m%dT%H%M%SZ")+".json"
    path=OUT/filename
    with path.open("x") as f:json.dump(card,f,indent=2)
    print("FRESH four-model card:",path,"games:",len(card["games"]),"changes:",len(card.get("changesFromOriginal",[])))
if __name__=="__main__":main()
