"""Read-only NFL four-model publication readiness audit. No predictions are generated."""
import argparse
import json
from pathlib import Path

MODELS=("A","B","C","C-QB")
def inspect(card, expected_ids):
    issues=[]
    if card is None:
        return ["FOUR_MODEL_CARD_NOT_FOUND"]
    games=card.get("games",[])
    if not isinstance(games,list):
        return ["INVALID_GAMES"]
    observed=[str(g.get("id","")) for g in games]
    expected={str(i) for i in expected_ids}
    if len(observed)!=len(set(observed)):
        issues.append("DUPLICATE_GAME_IDS")
    if set(observed)!=expected:
        issues.append("SCHEDULE_COVERAGE_MISMATCH missing=%s extra=%s" % (sorted(expected-set(observed)),sorted(set(observed)-expected)))
    for game in games:
        for model in MODELS:
            pick=(game.get("picks") or {}).get(model)
            if pick not in (game.get("home"),game.get("away")):
                issues.append("%s %s MISSING_MODEL_WINNER" % (game.get("id"),model))
    return issues

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--card",type=Path,required=True)
    p.add_argument("--schedule",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("nfl-publisher-readiness.json"))
    args=p.parse_args()
    try:
        schedule=json.loads(args.schedule.read_text())
        if not schedule.get("games"):
            raise ValueError("schedule has no games")
        card=json.loads(args.card.read_text()) if args.card.is_file() else None
        issues=inspect(card,[g["id"] for g in schedule["games"]])
    except (ValueError,KeyError,TypeError,OSError) as exc:
        issues=["INVALID_SCHEDULE_OR_CARD "+str(exc)]
    result={"status":"READY_FOR_REVIEW" if not issues else "BLOCKED","issues":issues,"read_only":True,"does_not_generate_picks":True}
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    raise SystemExit(bool(issues))

if __name__=="__main__":
    main()
