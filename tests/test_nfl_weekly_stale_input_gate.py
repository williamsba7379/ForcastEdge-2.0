"""Fail closed on stale Wednesday inputs without touching frozen records."""
import datetime as dt
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nfl_four_model_head_to_head as four

class StaleWeekGate(unittest.TestCase):
    def test_stale_week_8_refuses_write_for_week_10(self):
        now = dt.datetime.now(dt.timezone.utc)
        local = now.astimezone(ZoneInfo("America/New_York"))
        thursday = local.date() + dt.timedelta(days=(3-local.weekday()) % 7)
        kickoff = dt.datetime.combine(thursday, dt.time(20,15), tzinfo=ZoneInfo("America/New_York"))
        with tempfile.TemporaryDirectory() as tmp:
            data = pathlib.Path(tmp)
            (data / "nfl-schedule.json").write_text(json.dumps({"season":2026,"weeks":[{"week":10,"games":[{"id":"test","date":kickoff.isoformat(),"home":"Home","away":"Away"}]}]}))
            (data / "model-c-automated-draft.json").write_text(json.dumps({"season":2026,"week":8}))
            (data / "model-c-qb-shadow.json").write_text(json.dumps({"season":2026,"week":8}))
            (data / "nfl-historical-results.json").write_text("{}")
            out = data / "four-model-head-to-head"
            with patch.object(four,"DATA",data), patch.object(four,"OUT",out):
                with self.assertRaisesRegex(RuntimeError,"STALE_MODEL_INPUTS_REFUSE_FREEZE"):
                    four.main()
            self.assertFalse(out.exists())

if __name__ == "__main__":
    unittest.main()
