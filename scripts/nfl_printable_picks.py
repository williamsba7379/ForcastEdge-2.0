"""Produce a printable, shareable HTML report from archived NFL predictions only."""
import argparse
import html
import json
from pathlib import Path

MODELS=("A","B","C","C-QB")
def esc(x):
    return html.escape(str(x) if x is not None else "UNVERIFIED")
def render(card):
    games=card.get("games",[])
    out=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ForecastEdge NFL Printable Picks</title>',
    '<style>body{font:15px Arial,sans-serif;max-width:950px;margin:24px auto;padding:12px;color:#111}h1{font-size:24px}table{border-collapse:collapse;width:100%;margin:12px 0 24px}td,th{border:1px solid #888;padding:7px;text-align:left}th{background:#eee}.game{break-inside:avoid;margin:18px 0}small{color:#444}@media print{body{margin:0;font-size:11px}.game{break-inside:avoid}button{display:none}}</style>',
    '<h1>ForecastEdge NFL — Printable Weekly Picks</h1>',
    '<p>Season '+esc(card.get("season"))+' • Week '+esc(card.get("week"))+' • All times as archived (UTC). Frozen at '+esc(card.get("frozenAt"))+'</p>',
    '<p><strong>NO BET remains unchanged.</strong> UNVERIFIED means no reliable archived forecast or line. No missing picks are invented.</p>',
    '<button onclick="window.print()">Print / Save as PDF</button>']
    for game in sorted(games,key=lambda g:g.get("date","")):
        out.extend(['<section class="game"><h2>'+esc(game.get("away"))+' @ '+esc(game.get("home"))+'</h2><small>Kickoff: '+esc(game.get("date"))+'</small>',
                    '<table><thead><tr><th>Model</th><th>Winner / ML side</th><th>Projected score (Away–Home)</th><th>Spread</th><th>O/U</th><th>Confidence</th><th>Rating</th></tr></thead><tbody>'])
        for model in MODELS:
            forecast=(game.get("model_forecasts") or {}).get(model) or {}
            picks=game.get("picks") or {}
            def market(k):
                v=forecast.get(k)
                return esc(v.get("selection"))+" ("+esc(v.get("line"))+")" if isinstance(v,dict) and v.get("selection") else "UNVERIFIED"
            score=(esc(forecast.get("projected_away_score"))+"–"+esc(forecast.get("projected_home_score"))) if forecast.get("projected_away_score") is not None and forecast.get("projected_home_score") is not None else "UNVERIFIED"
            cells=[model,picks.get(model,"UNVERIFIED"),score,market("spread"),market("total"),forecast.get("confidence","UNVERIFIED"),"NO BET"]
            out.append("<tr>"+"".join("<td>"+esc(v)+"</td>" for v in cells)+"</tr>")
        out.append("</tbody></table></section>")
    out.append("<h2>Pool-only winners list</h2><p>Choose the verified model before distributing this list; no consensus winner is fabricated.</p><table><tr><th>Matchup</th>"+ "".join("<th>"+m+"</th>" for m in MODELS)+"</tr>")
    for game in sorted(games,key=lambda g:g.get("date","")):
        out.append("<tr><td>"+esc(game.get("away"))+" @ "+esc(game.get("home"))+"</td>"+"".join("<td>"+esc((game.get("picks") or {}).get(m,"UNVERIFIED"))+"</td>" for m in MODELS)+"</tr>")
    out.append("</table></html>")
    return "\n".join(out)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("card",type=Path)
    p.add_argument("--output",type=Path,default=Path("nfl-printable-picks.html"))
    args=p.parse_args()
    args.output.write_text(render(json.loads(args.card.read_text())),encoding="utf-8")
    print("Printable report created:",args.output)
if __name__=="__main__":
    main()
