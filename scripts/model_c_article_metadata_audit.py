#!/usr/bin/env python3
"""Audit actual official article metadata retrieval; never confirm a QB."""
import datetime as dt
import json
import pathlib

DATA=pathlib.Path(__file__).resolve().parents[1]/"data"

def audit(metadata,queue):
    games={(g["gameId"],g["team"]):g for g in queue["items"]}
    records=[]
    for item in metadata["items"]:
        game=games.get((item["gameId"],item["team"]))
        state="UNKNOWN_GAME"
        if item.get("fetchStatus")!="OK":state="FETCH_FAILED"
        elif not item.get("publishedAt"):state="DATE_UNVERIFIED"
        elif game:
            try:
                published=dt.datetime.fromisoformat(item["publishedAt"])
                kickoff=dt.datetime.fromisoformat(game["kickoff"].replace("Z","+00:00"))
                if published.tzinfo is None:state="DATE_UNVERIFIED"
                elif published>kickoff:state="AFTER_KICKOFF"
                elif kickoff-published<=dt.timedelta(days=7):state="WITHIN_SEVEN_DAYS"
                else:state="OLDER_THAN_SEVEN_DAYS"
            except (ValueError,TypeError):state="DATE_UNVERIFIED"
        records.append({"gameId":item["gameId"],"team":item["team"],"url":item["url"],
                        "publicationWindow":state,"starterConfirmed":False})
    counts={state:sum(x["publicationWindow"]==state for x in records) for state in
            ("WITHIN_SEVEN_DAYS","OLDER_THAN_SEVEN_DAYS","AFTER_KICKOFF","DATE_UNVERIFIED","FETCH_FAILED","UNKNOWN_GAME")}
    return {"status":"ARTICLE_METADATA_AUDIT_ONLY","automaticConfirmations":0,
            "totalArticles":len(records),"counts":counts,"items":records,
            "note":"Publication date alone does not establish quarterback or matchup relevance."}

if __name__=="__main__":
    metadata=json.loads((DATA/"model-c-official-article-metadata.json").read_text())
    queue=json.loads((DATA/"model-c-qb-review-queue.json").read_text())
    output=audit(metadata,queue)
    (DATA/"model-c-article-metadata-audit.json").write_text(json.dumps(output,indent=2)+"\n")
    print("Article metadata audit:",output["counts"])
