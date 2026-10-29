#!/usr/bin/env python3
"""Compare experimental projected totals to sourced, pregame sportsbook totals.
Never fabricate lines, backfill a post-snapshot quote, or claim calibrated edges.
"""
import json
import pathlib
from nfl_four_model_head_to_head import DATA, OUT, stamp

def compare(research, market):
    if (research["season"],research["week"]) != (market.get("season"),market.get("week")):
        raise ValueError("Market week mismatch")
    by_id={str(g["id"]):g for g in research["games"]}
    seen=set()
    for quote in market.get("games",[]):
        key=str(quote.get("id",""))
        if key not in by_id or key in seen:raise ValueError("Unknown or duplicate game: "+key)
        seen.add(key)
        total=quote.get("total")
        source=quote.get("source")
        asof=quote.get("capturedAt")
        if type(total) not in (float,int) or not 10<=total<=100 or not isinstance(source,str) or not source.startswith("https://") or not asof:
            raise ValueError("Missing valid sourced market total: "+key)
        row=by_id[key]
        if stamp(asof)>stamp(research["sourceComparisonFrozenAt"]):
            raise ValueError("Market quote later than frozen prediction snapshot: "+key)
        if stamp(asof)>=stamp(row["date"]):
            raise ValueError("Market quote after kickoff: "+key)
        for prediction in row["models"].values():
            projected=prediction.get("projectedTotal")
            prediction["marketTotal"]=total
            prediction["marketSource"]=source
            prediction["marketCapturedAt"]=asof
            if projected is not None:
                edge=round(projected-total,1)
                prediction["totalDifference"]=edge
                prediction["overUnderPick"]="OVER" if edge>0 else "UNDER" if edge<0 else "PUSH"
    research["marketLinesAvailable"]=len(seen)
    research["status"]="EXPERIMENTAL_SOURCED_MARKET_COMPARISON" if seen else "NO_SOURCED_MARKET_LINES"
    research["warning"]="Uncalibrated experimental totals, not wagering advice. No pick without sourced, timestamped pregame market line."
    return research

def main():
    source=DATA/"nfl-market-totals.json"
    files=sorted(OUT.glob("*-totals-research.json"))
    if not files:raise ValueError("No projected totals research file yet")
    report=json.loads(files[-1].read_text())
    if source.exists():
        quotes=json.loads(source.read_text())
    else:
        quotes={"season":report["season"],"week":report["week"],"games":[]}
    result=compare(report,quotes)
    output=OUT/(str(report["season"])+"-week-"+str(report["week"])+"-totals-market-comparison.json")
    output.write_text(json.dumps(result,indent=2)+"\n")
    print("Market totals:",result["marketLinesAvailable"],"of",len(result["games"]))
if __name__=="__main__":main()
