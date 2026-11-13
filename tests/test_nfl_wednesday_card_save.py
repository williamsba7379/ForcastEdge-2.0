"""Offline rehearsal of validating and saving a complete Wednesday test card."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from research.nfl_delivery_failclosed import ET, MODELS, parse, validate


def save_test_card(workspace, schedule, card, source, qb, markets, timestamp):
    now = parse(timestamp)
    eastern = now.astimezone(ET)
    if eastern.weekday() != 2 or eastern > eastern.replace(
        hour=11, minute=0, second=0, microsecond=0
    ):
        raise ValueError("Outside the Wednesday delivery window")
    result = validate(schedule, card, now, source_evidence=source, qb_evidence=qb)
    if result["status"] != "PASS":
        raise ValueError("Incomplete four-model card")
    if set(markets) != {game["id"] for game in card["games"]}:
        raise ValueError("Incomplete market coverage")
    for game in card["games"]:
        market = markets[game["id"]]
        if (
            (market.get("season"), market.get("week")) != (card["season"], card["week"])
            or any(market.get(key) != game[key] for key in ("away", "home", "date"))
            or any(type(market.get(key)) not in (int, float) for key in ("spread", "total"))
            or not market.get("provider")
            or not eastern.replace(hour=0, minute=0, second=0, microsecond=0)
            <= parse(market["capturedAt"]) <= now
        ):
            raise ValueError("Mismatched or late market evidence")
    record = {
        "status": "SYNTHETIC_REHEARSAL_ONLY",
        "savedAt": now.isoformat(),
        "card": card,
        "modelEvidence": source,
        "qbEvidence": qb,
        "markets": markets,
    }
    path = workspace / "synthetic-wednesday-card.json"
    payload = json.dumps(record, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as output:
        output.write(payload)
    return path


class WednesdayCardSaveTests(unittest.TestCase):
    cutoff = "2026-11-11T16:00:00Z"

    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.workspace = Path(workspace.name)
        games = [
            {"id": str(i), "away": f"Away {i}", "home": f"Home {i}",
             "date": (dt.datetime(2026, 11, 15, 18, tzinfo=dt.timezone.utc)
                      + dt.timedelta(minutes=i)).isoformat()}
            for i in range(14)
        ]
        self.schedule = {"season": 2026, "weeks": [{"week": 10, "games": games}]}
        self.card = {"season": 2026, "week": 10, "games": [
            dict(game, picks={model: game["home"] for model in MODELS}, wager="NO BET")
            for game in games
        ]}
        self.source = {
            game["id"]: {
                model: {"projectedAwayScore": 17, "projectedHomeScore": 20,
                        "projectedMargin": 3, "projectedTotal": 37,
                        "modelArtifactId": f"fixture-{model}", "engineSha256": "a" * 64,
                        "inputSha256": "b" * 64, "generatedAt": "2026-11-11T15:50:00Z"}
                for model in MODELS
            }
            for game in games
        }
        self.qb = {
            game["id"]: {model: {"officialGameSpecific": True} for model in ("C", "C-QB")}
            for game in games
        }
        self.markets = {
            game["id"]: dict(game, season=2026, week=10, spread=-2.5, total=39.5,
                             provider="Synthetic fixture", capturedAt="2026-11-11T15:55:00Z")
            for game in games
        }

    def save(self, timestamp=None):
        return save_test_card(
            self.workspace, self.schedule, self.card, self.source, self.qb,
            self.markets, timestamp or self.cutoff,
        )

    def assert_blocked(self, reason, timestamp=None):
        with self.assertRaisesRegex(ValueError, reason):
            self.save(timestamp)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_complete_card_round_trips_at_cutoff_and_cannot_be_overwritten(self):
        path = self.save()
        original = path.read_bytes()
        record = json.loads(original)
        self.assertEqual(record["status"], "SYNTHETIC_REHEARSAL_ONLY")
        self.assertEqual(record["savedAt"], "2026-11-11T16:00:00+00:00")
        self.assertEqual(record["card"], self.card)
        self.assertEqual(record["modelEvidence"], self.source)
        self.assertEqual(record["qbEvidence"], self.qb)
        self.assertEqual(record["markets"], self.markets)
        self.assertEqual(sum(len(game["picks"]) for game in record["card"]["games"]), 56)
        with self.assertRaises(FileExistsError):
            self.save()
        self.assertEqual(path.read_bytes(), original)

    def test_late_delivery_is_blocked(self):
        self.assert_blocked("Wednesday delivery window", "2026-11-11T16:00:01Z")

    def test_missing_model_row_is_blocked(self):
        del self.card["games"][0]["picks"]["B"]
        self.assert_blocked("Incomplete four-model card")

    def test_missing_qb_evidence_is_blocked(self):
        del self.qb["0"]["C-QB"]
        self.assert_blocked("Incomplete four-model card")

    def test_stale_card_is_blocked(self):
        self.card["week"] = 8
        self.assert_blocked("Incomplete four-model card")

    def test_missing_market_is_blocked(self):
        del self.markets["0"]
        self.assert_blocked("Incomplete market coverage")

    def test_wrong_week_market_is_blocked(self):
        self.markets["0"]["week"] = 8
        self.assert_blocked("Mismatched or late market evidence")

    def test_late_market_is_blocked(self):
        self.markets["0"]["capturedAt"] = "2026-11-11T16:00:01Z"
        self.assert_blocked("Mismatched or late market evidence")
