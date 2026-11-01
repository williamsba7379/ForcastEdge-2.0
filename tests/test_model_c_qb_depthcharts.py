#!/usr/bin/env python3
"""Offline depth-chart contract test, no live ESPN request."""
import importlib.util
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("qbdepth",ROOT/"scripts/model_c_qb_depthcharts.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def main():
    example={"depthchart":[{"positions":{"qb":{"position":{"abbreviation":"QB"},
       "athletes":[{"rank":1,"athlete":{"displayName":"Fixture QB One"}},
                   {"rank":2,"athlete":{"displayName":"Fixture QB Two"}}]},
       "rb":{"position":{"abbreviation":"RB"},
       "athletes":[{"rank":1,"athlete":{"displayName":"Fixture RB"}}]}}}]}
    assert module.extract_qbs(example)==["Fixture QB One"]
    alternate={"depthcharts":[{"positions":[{"position":{"abbreviation":"QB"},
        "athletes":[{"depthOrder":1,"athlete":{"displayName":"Fixture QB One"}},
                    {"depthOrder":2,"athlete":{"displayName":"Fixture QB Two"}}]}]}]}
    assert module.extract_qbs(alternate)==["Fixture QB One"]
    mapping={"depthchart":{"offense":{"positions":{"qb":{"abbreviation":"QB",
        "athletes":[{"depth":1,"displayName":"Fixture QB One"}]}}}}}
    assert module.extract_qbs(mapping)==["Fixture QB One"]
    # Do not treat an unranked quarterback or QB2 as a verified QB1 candidate.
    unranked={"depthchart":[{"positions":[{"position":{"abbreviation":"QB"},
        "athletes":[{"athlete":{"displayName":"Unranked QB"}},
                    {"rank":2,"athlete":{"displayName":"Backup QB"}}]}]}]}
    assert module.extract_qbs(unranked)==[]
    assert module.extract_qbs({"depthchart":[]})==[]
    # Bounded diagnostic must not print any player data or infer QB1.
    secret = "PRIVATE_PLAYER_NAME_987"
    payload = {"depthchart": [{"section": {"positions": [{"athletes": [{"displayName": secret}]}]},
                              "athletes": [{"displayName": secret}]}]}
    shape = module.describe_depthchart_shape(payload)
    assert shape["depthchartType"] == "list"
    assert shape["sampleCharts"][0]["fields"]["section"]["keys"] == ["positions"]
    assert shape["sampleCharts"][0]["fields"]["athletes"]["firstKeys"] == ["displayName"]
    assert secret not in __import__("json").dumps(shape)
    assert module.extract_qbs(payload) == []
    assert len(module.describe_depthchart_shape({"depthchart": [{}] * 9})["sampleCharts"]) == 2
    # ESPN keyed-position fixture: key identifies QB, but record lacks position metadata.
    keyed={"depthchart":[{"positions":{"qb":{"athletes":[
        {"rank":1,"athlete":{"displayName":"Keyed QB One"}},
        {"rank":2,"athlete":{"displayName":"Keyed QB Two"}}]},
        "rb":{"athletes":[{"rank":1,"athlete":{"displayName":"Running Back"}}]}}}]}
    assert module.extract_qbs(keyed)==["Keyed QB One"]
    keyed["depthchart"][0]["positions"]["qb"]["athletes"][0].pop("rank")
    assert module.extract_qbs(keyed)==[]
    shape_keyed=module.describe_depthchart_shape(keyed)
    assert "athletes" in shape_keyed["qbShapes"][0]["keys"]
    assert shape_keyed["qbShapes"][0]["athletes"]["firstKeys"]==["athlete"]
    assert "Keyed QB One" not in __import__("json").dumps(shape_keyed)
    print("PASS: keyed QB extraction, explicit rank safeguards and bounded shape-only diagnostics")

if __name__=="__main__":main()
