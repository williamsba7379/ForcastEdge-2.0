#!/usr/bin/env python3
"""Build a review-only printable HTML report from existing four-model winner cards.
No invented odds, confidence, scores, wagers, or publication side effects.
"""
import argparse
import html
import json
from pathlib import Path

MODELS = ("A", "B", "C", "C-QB")
MISSING = "NOT AVAILABLE"


def build(card, research=None):
    if not isinstance(card, dict) or not isinstance(card.get("games"), list):
        raise ValueError("Four-model card games required")
    if research is not None and (research.get("season"), research.get("week")) != (card.get("season"), card.get("week")):
        raise ValueError("Research week mismatch")
    research_rows = {str(g["id"]): g for g in (research or {}).get("games", [])}
    games = []
    for game in card["games"]:
        picks = game.get("picks", {})
        if set(picks) != set(MODELS):
            raise ValueError("All four independent model winners required")
        item = {"id": str(game["id"]), "home": game["home"], "away": game["away"],
                "date": game["date"], "models": {}}
        for model in MODELS:
            if picks[model] not in (game["home"], game["away"]):
                raise ValueError("Winner not in matchup")
            extra = research_rows.get(str(game["id"]), {}).get("models", {}).get(model, {})
            # Scores are explicitly experimental and only shown when actually present.
            item["models"][model] = {
                "winner": picks[model], "spread": MISSING, "spreadLine": MISSING,
                "overUnder": MISSING, "marketTotal": MISSING,
                "projectedAway": extra.get("projectedAway", MISSING),
                "projectedHome": extra.get("projectedHome", MISSING),
                "confidence": MISSING, "wagerStatus": "NO BET",
                "projectionStatus": extra.get("status", "NO PROJECTION")}
        games.append(item)
    return {"season": card.get("season"), "week": card.get("week"),
            "sourceStatus": card.get("status", "UNVERIFIED"),
            "sourceFrozenAt": card.get("frozenAt"), "status": "REVIEW_ONLY_INCOMPLETE",
            "notice": "Not official. Winner-only model comparisons; market lines, spread and total picks, and calibrated confidence are not supplied.",
            "games": games}


def render(report):
    e = lambda v: html.escape(str(v), quote=True)
    lines = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>ForecastEdge four-model review report</title>',
             '<style>body{font:16px system-ui;max-width:950px;margin:auto;padding:20px;color:#111}'
             'table{width:100%;border-collapse:collapse;margin-bottom:24px}'
             'th,td{border:1px solid #777;padding:7px;text-align:left}'
             'h2{break-before:page} .warning{font-weight:bold}'
             '@media print{button{display:none}body{padding:0}tr{break-inside:avoid}}</style>',
             '<h1>ForecastEdge NFL — Four-model review report</h1>',
             '<p class="warning">REVIEW ONLY — INCOMPLETE — NOT OFFICIAL — NO BET</p>',
             '<p>'+e(report["notice"])+'</p>',
             '<p>Season '+e(report["season"])+' · Week '+e(report["week"])+' · Source: '+e(report["sourceStatus"])+'</p>',
             '<button onclick="window.print()">Print report</button>']
    for game in report["games"]:
        lines.extend(['<h2>'+e(game["away"])+' @ '+e(game["home"])+'</h2>',
                      '<p>Kickoff: '+e(game["date"])+' · Game ID: '+e(game["id"])+'</p>',
                      '<table><thead><tr><th>Model</th><th>Winner</th><th>Spread</th><th>Total</th><th>Projected score (away–home)</th><th>Confidence</th><th>Status</th></tr></thead><tbody>'])
        for model in MODELS:
            row = game["models"][model]
            score = e(row["projectedAway"])+' – '+e(row["projectedHome"])
            lines.append('<tr><td>'+e(model)+'</td><td>'+e(row["winner"])+'</td><td>'+e(row["spread"])+'</td><td>'+e(row["overUnder"])+'</td><td>'+score+'</td><td>'+e(row["confidence"])+'</td><td>NO BET · '+e(row["projectionStatus"])+'</td></tr>')
        lines.append('</tbody></table>')
    lines.append('</html>')
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--card", required=True, type=Path)
    p.add_argument("--research", type=Path)
    p.add_argument("--html", required=True, type=Path)
    p.add_argument("--json", type=Path, help="Optional review-only JSON output; never auto-publish")
    args = p.parse_args()
    card = json.loads(args.card.read_text())
    research = json.loads(args.research.read_text()) if args.research else None
    report = build(card, research)
    args.html.write_text(render(report), encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
    print("REVIEW_ONLY_INCOMPLETE; no official card published")


if __name__ == "__main__":
    main()
