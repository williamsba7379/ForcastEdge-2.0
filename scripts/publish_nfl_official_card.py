#!/usr/bin/env python3
"""Nonproduction artifact preparation only. No GitHub writes, no latest pointer, no network."""
import html
import json
import os
from pathlib import Path
from validate_nfl_official_card import validate_files

def printable(card):
    def e(value): return html.escape(str(value), quote=True)
    lines = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ForecastEdge NFL official card</title>',
             '<style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #888;padding:7px;text-align:left}@media print{body{margin:8mm}}</style></head><body>',
             '<h1>ForecastEdge NFL — Four-model frozen card</h1>',
             '<p>Season '+e(card["season"])+' Week '+e(card["week"])+' | '+e(card["status"])+' | Frozen '+e(card["frozenAt"])+' | Published '+e(card["publishedAt"])+'</p>',
             '<p>Card ID: '+e(card["cardId"])+' | SHA-256: '+e(card["cardHash"])+'</p>',
             '<table><thead><tr><th>Game</th><th>Model</th><th>Winner</th><th>Spread</th><th>Total</th><th>Projected final</th><th>Confidence</th><th>Wager</th></tr></thead><tbody>']
    for g in card["games"]:
        for name in ("A","B","C","C-QB"):
            m=g["models"][name]
            vals=[g["awayTeam"]+" @ "+g["homeTeam"],name,m["moneylineWinner"],m["spreadPick"]+" ("+str(m["spreadLine"])+")",m["totalPick"]+" ("+str(m["totalLine"])+")",str(m["projectedAwayScore"])+"–"+str(m["projectedHomeScore"]),m["confidence"],m["wagerStatus"]]
            lines.append("<tr>"+"".join("<td>"+e(x)+"</td>" for x in vals)+"</tr>")
    lines.append("</tbody></table></body></html>")
    return "\n".join(lines)+"\n"
def prepare(card_path, schedule_path, schema_path, output_dir):
    if os.environ.get("FORECASTEDGE_RESEARCH_PREPARE") != "EXPLICIT_LOCAL_ONLY":
        raise RuntimeError("Research preparation disabled without explicit local opt-in")
    card=validate_files(card_path,schedule_path,schema_path)
    target=Path(output_dir).resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError("Refuse to overwrite existing output")
    target.mkdir(parents=True,exist_ok=True)
    name=str(card["season"])+"-week-"+str(card["week"])
    (target/(name+".json")).write_text(json.dumps(card,indent=2)+"\n")
    (target/(name+".html")).write_text(printable(card))
    # Never write latest.json, production directories, git refs or GitHub APIs.
    return name
