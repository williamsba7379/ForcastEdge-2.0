"""Synthetic contract assertions only. No tests executed; no external NFL data."""
import copy
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from scripts.validate_nfl_official_card import canonical, digest, validate

class ContractTests(unittest.TestCase):
    def setUp(self):
        cutoff=dt.datetime(2026,11,18,11,tzinfo=ZoneInfo("America/New_York"))
        self.cutoff=cutoff.isoformat()
        self.frozen=(cutoff-dt.timedelta(minutes=5)).isoformat()
        self.published=(cutoff-dt.timedelta(minutes=1)).isoformat()
        kickoff=(cutoff+dt.timedelta(days=1,hours=8)).isoformat()
        self.schedule={"season":2026,"week":11,"games":[{"id":"synthetic-1","home":"HOME","away":"AWAY","date":kickoff}]}
        self.trusted={}
        def evidence(name):
            e={"source":"synthetic","artifactId":name,"capturedAt":(cutoff-dt.timedelta(hours=1)).isoformat(),"sha256":"a"*64}
            self.trusted[("synthetic",name)]=copy.deepcopy(e)
            return e
        model={"moneylineWinner":"HOME","spreadPick":"HOME","spreadLine":-1.5,"totalPick":"OVER","totalLine":41.5,"projectedHomeScore":24,"projectedAwayScore":20,"confidence":0.6,"wagerStatus":"NO BET","marketEvidence":evidence("market"),"modelEvidence":evidence("model")}
        self.card={"schemaVersion":"1.0","cardId":"synthetic-only","season":2026,"week":11,"status":"FROZEN_ON_TIME","deliveryStatus":"DELIVERED_ON_TIME","cutoffAt":self.cutoff,"frozenAt":self.frozen,"publishedAt":self.published,"publisherId":"nfl-official-wednesday","inputManifestHash":digest(self.schedule),"games":[{"gameId":"synthetic-1","kickoffAt":kickoff,"homeTeam":"HOME","awayTeam":"AWAY","qbEvidence":evidence("qb"),"models":{name:copy.deepcopy(model) for name in ("A","B","C","C-QB")}}],"releaseEvidence":{"authorityId":"synthetic-independent","manifestSha256":"b"*64,"approvedAt":self.published,"signature":"synthetic-signature","keyId":"synthetic-key"}}
        self.schema={"required":list(self.card)+["cardHash"],"$defs":{"model":{"required":list(model)},"releaseEvidence":{"required":list(self.card["releaseEvidence"])}}}
        self.seal()
    def seal(self):
        self.card["cardHash"]=digest({k:v for k,v in self.card.items() if k!="cardHash"})
    def verify(self,card=None,authority=lambda *_:True):
        return validate(self.card if card is None else card,self.schedule,self.schema,trusted_evidence=self.trusted,verify_release=authority)
    def test_complete_synthetic_card(self):
        self.assertTrue(self.verify())
    def test_missing_model_fails(self):
        del self.card["games"][0]["models"]["C-QB"];self.seal()
        with self.assertRaises(ValueError):self.verify()
    def test_untrusted_evidence_fails(self):
        self.trusted.clear()
        with self.assertRaises(ValueError):self.verify()
    def test_untrusted_release_fails(self):
        with self.assertRaises(ValueError):self.verify(authority=lambda *_:False)
    def test_wrong_week_fails(self):
        self.card["week"]=12;self.seal()
        with self.assertRaises(ValueError):self.verify()
    def test_late_delivery_fails_mislabel(self):
        self.card["publishedAt"]=(dt.datetime.fromisoformat(self.cutoff)+dt.timedelta(minutes=1)).isoformat();self.seal()
        with self.assertRaises(ValueError):self.verify()
    def test_tamper_fails(self):
        self.card["games"][0]["models"]["A"]["confidence"]=0.9
        with self.assertRaises(ValueError):self.verify()
    def test_missing_authority_fails(self):
        with self.assertRaises(ValueError):validate(self.card,self.schedule,self.schema)
    def test_extra_model_fails(self):
        self.card["games"][0]["models"]["X"]=copy.deepcopy(self.card["games"][0]["models"]["A"]);self.seal()
        with self.assertRaises(ValueError):self.verify()
    def test_wrong_slate_cutoff_fails(self):
        self.card["cutoffAt"]=(dt.datetime.fromisoformat(self.cutoff)-dt.timedelta(days=7)).isoformat();self.seal()
        with self.assertRaises(ValueError):self.verify()
