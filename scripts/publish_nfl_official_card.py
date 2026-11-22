#!/usr/bin/env python3
"""Disabled research-only artifact preparation; no network, git, pointer or publication."""
import html
import json
import os
import stat
from pathlib import Path
from validate_nfl_official_card import validate_files

def printable(card):
    esc=lambda value:html.escape(str(value),quote=True)
    lines=['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ForecastEdge research card</title>',
           '<style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #888;padding:7px;text-align:left}@media print{body{margin:8mm}}</style></head><body>',
           '<h1>NONPRODUCTION RESEARCH CARD — NOT PUBLISHED</h1>',
           '<p>Season '+esc(card["season"])+' Week '+esc(card["week"])+' | '+esc(card["status"])+' | '+esc(card["deliveryStatus"])+'</p>',
           '<p>Frozen '+esc(card["frozenAt"])+' | Recorded publication '+esc(card["publishedAt"])+' | Card '+esc(card["cardId"])+' | SHA-256 '+esc(card["cardHash"])+'</p>',
           '<table><thead><tr><th>Game</th><th>Model</th><th>Winner</th><th>Spread</th><th>Total</th><th>Projected final</th><th>Confidence</th><th>Wager</th></tr></thead><tbody>']
    for game in card["games"]:
        for name in ("A","B","C","C-QB"):
            m=game["models"][name]
            vals=[game["awayTeam"]+" @ "+game["homeTeam"],name,m["moneylineWinner"],m["spreadPick"]+" ("+str(m["spreadLine"])+")",m["totalPick"]+" ("+str(m["totalLine"])+")",str(m["projectedAwayScore"])+"–"+str(m["projectedHomeScore"]),m["confidence"],m["wagerStatus"]]
            lines.append("<tr>"+"".join("<td>"+esc(v)+"</td>" for v in vals)+"</tr>")
    return "\n".join(lines+["</tbody></table></body></html>"])+"\n"

def prepare(card_path,schedule_path,schema_path,output_dir,*,trusted_evidence=None,verify_release=None):
    if os.environ.get("FORECASTEDGE_RESEARCH_PREPARE")!="EXPLICIT_LOCAL_ONLY":
        raise RuntimeError("Research preparation disabled")
    # An environment variable is not a security boundary: require a caller-supplied
    # independently verified release and an explicitly configured research root.
    root=os.environ.get("FORECASTEDGE_DISPOSABLE_RESEARCH_ROOT")
    if not root:
        raise ValueError("Missing disposable research root")
    root=Path(root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink() or (root.stat().st_mode & 0o022):
        raise ValueError("Unsafe research root")
    target=Path(output_dir)
    if not target.is_absolute() or target.is_symlink() or target.exists() or target.parent.resolve(strict=True)!=root:
        raise ValueError("Output must be a new direct child of disposable research root")
    card=validate_files(card_path,schedule_path,schema_path,trusted_evidence=trusted_evidence,verify_release=verify_release)
    name=str(card["season"])+"-week-"+str(card["week"])
    target.mkdir(mode=0o700)
    # No overwrite and no following symlinks. No latest pointer, GitHub write or production path.
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW
    for filename,content in ((name+".json",json.dumps(card,indent=2)+"\n"),(name+".html",printable(card))):
        fd=os.open(target/filename,flags,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    return name
