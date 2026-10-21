#!/usr/bin/env python3
"""Offline QB feed contract smoke test: no external requests."""
import importlib.util
import json
import pathlib
import tempfile
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("qbfeed",ROOT/"scripts/model_c_qb_stats.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test():
    with tempfile.TemporaryDirectory() as tmp:
        directory=pathlib.Path(tmp)
        (directory/"nfl-schedule.json").write_text(json.dumps({"season":2026,"weeks":[{"week":1}]}))
        mod.DATA=directory
        board={"events":[{"id":"fixture-1","date":"2026-09-10T20:00:00Z","status":{"type":{"completed":True}}}]}
        summary={"boxscore":{"players":[{"team":{"displayName":"Example Team"},"statistics":[
          {"name":"passing","labels":["C/ATT","YDS","TD","INT"],"athletes":[
          {"athlete":{"displayName":"Player One"},"stats":["18/25","240","2","1"]},
          {"athlete":{"displayName":"Player Two"},"stats":["1/2","8","0","0"]}]}]}]}}
        with patch.object(mod,"fetch",side_effect=lambda url:summary if "/summary?" in url else board):
            mod.main()
        stats=json.loads((directory/"model-c-qb-performance.json").read_text())
        candidates=json.loads((directory/"model-c-qb-candidates.json").read_text())
        assert stats["teams"]["Example Team"]["Player One"]["passAttempts"]==25
        assert candidates["teams"]["Example Team"]["candidate"]=="Player One"
        assert candidates["teams"]["Example Team"]["verification"]=="LAST_COMPLETED_GAME_ONLY"
        assert "starter" not in candidates["teams"]["Example Team"]
        print("PASS: fixture QB totals and unconfirmed candidate extraction")

if __name__=="__main__":
    test()
