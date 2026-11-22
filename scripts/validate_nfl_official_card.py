#!/usr/bin/env python3
"""Fail-closed research contract: independent manifest verifier required, no live publication."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

MODELS = ("A", "B", "C", "C-QB")
PUBLISHER = "nfl-official-wednesday"
SHA = set("0123456789abcdef")
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def timestamp(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing timestamp")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return t.astimezone(dt.timezone.utc)
def sha(value):
    return isinstance(value,str) and len(value)==64 and all(c in SHA for c in value)
def evidence(value, frozen, trusted):
    if not isinstance(value,dict) or set(value)!={"source","capturedAt","sha256","artifactId"}:
        raise ValueError("Evidence fields missing or unexpected")
    if not isinstance(value["source"],str) or not value["source"].strip() or not isinstance(value["artifactId"],str) or not value["artifactId"].strip() or not sha(value["sha256"]):
        raise ValueError("Invalid evidence")
    if timestamp(value["capturedAt"])>frozen:
        raise ValueError("Evidence postdates freeze")
    # Trusted evidence must be obtained from a separately controlled manifest, never the card.
    key=(value["source"],value["artifactId"])
    record=trusted.get(key)
    if record is None or record["sha256"]!=value["sha256"] or timestamp(record["capturedAt"])!=timestamp(value["capturedAt"]):
        raise ValueError("Unverified evidence")
def validate(card, schedule, schema, *, trusted_evidence=None, verify_release=None):
    if trusted_evidence is None or not callable(verify_release):
        raise ValueError("Independent manifest and release authority required")
    if not isinstance(card,dict) or not isinstance(schedule,dict) or set(card)!=set(schema["required"]):
        raise ValueError("Invalid card contract")
    if card["schemaVersion"]!="1.0" or card["publisherId"]!=PUBLISHER:
        raise ValueError("Unexpected schema or publisher")
    if type(card["season"]) is not int or card["season"]<2020 or type(card["week"]) is not int or not 1<=card["week"]<=18:
        raise ValueError("Invalid season/week")
    if not isinstance(card["cardId"],str) or not card["cardId"].strip():
        raise ValueError("Missing card ID")
    if (card["season"],card["week"])!=(schedule.get("season"),schedule.get("week")):
        raise ValueError("Wrong slate")
    cutoff,frozen,published=map(timestamp,(card["cutoffAt"],card["frozenAt"],card["publishedAt"]))
    local=cutoff.astimezone(ZoneInfo("America/New_York"))
    if local.weekday()!=2 or (local.hour,local.minute,local.second,local.microsecond)!=(11,0,0,0):
        raise ValueError("Wrong Wednesday cutoff")
    if published<frozen:
        raise ValueError("Publication before freeze")
    if card["status"]!=("FROZEN_ON_TIME" if frozen<=cutoff else "FROZEN_LATE"):
        raise ValueError("Incorrect freeze status")
    if card["deliveryStatus"]!=("DELIVERED_ON_TIME" if published<=cutoff else "DELIVERED_LATE"):
        raise ValueError("Incorrect delivery status")
    if not sha(card["inputManifestHash"]) or card["inputManifestHash"]!=digest(schedule):
        raise ValueError("Schedule digest mismatch")
    if not isinstance(schedule.get("games"),list) or not schedule["games"] or not isinstance(card["games"],list):
        raise ValueError("Missing schedule or card games")
    reference={str(g["id"]):g for g in schedule["games"]}
    ids=[g.get("gameId") for g in card["games"]]
    if len(reference)!=len(schedule["games"]) or len(ids)!=len(set(ids)) or set(ids)!=set(reference):
        raise ValueError("Incomplete or duplicate games")
    kickoffs=[timestamp(g["date"]) for g in schedule["games"]]
    if min(kickoffs)<=cutoff or max(kickoffs)>cutoff+dt.timedelta(days=6):
        raise ValueError("Games outside approved Thursday–Monday slate")
    if any(t.astimezone(ZoneInfo("America/New_York")).weekday() not in (3,4,5,6,0) for t in kickoffs):
        raise ValueError("Schedule contains game outside Thursday–Monday")
    for game in card["games"]:
        if set(game)!={"gameId","kickoffAt","homeTeam","awayTeam","qbEvidence","models"}:
            raise ValueError("Unexpected game fields")
        source=reference[game["gameId"]]
        if (game["homeTeam"],game["awayTeam"])!=(source["home"],source["away"]) or timestamp(game["kickoffAt"])!=timestamp(source["date"]):
            raise ValueError("Game identity mismatch")
        if timestamp(game["kickoffAt"])<=frozen:
            raise ValueError("Freeze after kickoff")
        evidence(game["qbEvidence"],frozen,trusted_evidence)
        if not isinstance(game["models"],dict) or set(game["models"])!=set(MODELS):
            raise ValueError("Four models required")
        for name in MODELS:
            m=game["models"][name]
            required=set(schema["$defs"]["model"]["required"])
            if not isinstance(m,dict) or set(m)!=required:
                raise ValueError("Invalid model fields")
            if m["moneylineWinner"] not in (game["homeTeam"],game["awayTeam"]) or m["spreadPick"] not in (game["homeTeam"],game["awayTeam"]):
                raise ValueError("Invalid team selection")
            if m["totalPick"] not in ("OVER","UNDER") or m["wagerStatus"]!="NO BET":
                raise ValueError("Unapproved total or wager")
            for field in ("spreadLine","totalLine","projectedHomeScore","projectedAwayScore","confidence"):
                v=m[field]
                if type(v) not in (float,int) or not math.isfinite(v):
                    raise ValueError("Invalid numeric field")
            if min(m["projectedHomeScore"],m["projectedAwayScore"])<0 or not 0<=m["confidence"]<=1:
                raise ValueError("Invalid projection")
            evidence(m["marketEvidence"],frozen,trusted_evidence)
            evidence(m["modelEvidence"],frozen,trusted_evidence)
    if not sha(card["cardHash"]) or card["cardHash"]!=digest({k:v for k,v in card.items() if k!="cardHash"}):
        raise ValueError("Card hash mismatch")
    release=card["releaseEvidence"]
    if not isinstance(release,dict) or set(release)!=set(schema["$defs"]["releaseEvidence"]["required"]):
        raise ValueError("Invalid release evidence")
    if not sha(release["manifestSha256"]) or timestamp(release["approvedAt"])<frozen:
        raise ValueError("Invalid release timestamp or manifest hash")
    if verify_release(card,schedule,release) is not True:
        raise ValueError("Independent release verification failed")
    return True

def validate_files(card_path,schedule_path,schema_path,*,trusted_evidence=None,verify_release=None):
    card=json.loads(Path(card_path).read_text())
    schedule=json.loads(Path(schedule_path).read_text())
    schema=json.loads(Path(schema_path).read_text())
    validate(card,schedule,schema,trusted_evidence=trusted_evidence,verify_release=verify_release)
    return card
