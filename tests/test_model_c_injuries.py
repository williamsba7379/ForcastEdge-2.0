#!/usr/bin/env python3
"""Offline checks for Model C injury-to-team mapping."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/model_c_injuries.py"
spec = importlib.util.spec_from_file_location("model_c_injuries", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

player = {"athlete": {"displayName": "Sample QB", "position": {"abbreviation": "QB"}},
          "status": "Questionable"}
nested = {"injuries": [{"team": {"displayName": "Chicago Bears", "id": "3"},
                         "injuries": [player]}]}
flat = {"injuries": [{"displayName": "Chicago Bears", "id": "3",
                       "injuries": [player]}]}
for payload in (nested, flat):
    teams = module.parse_groups(payload)
    assert len(teams) == 1
    assert teams[0]["team"] == "Chicago Bears"
    assert teams[0]["players"][0]["name"] == "Sample QB"

try:
    module.parse_groups({"injuries": [{"injuries": [player]}]})
    raise AssertionError("Unassigned injury group must be rejected")
except RuntimeError:
    pass
print("PASS: team mapping for nested/flat ESPN payloads; reject unassigned group")
