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
    # Do not treat an unranked quarterback or QB2 as a verified QB1 candidate.\n    unranked={"depthchart":[{"positions":[{"position":{"abbreviation":"QB"},\n        "athletes":[{"athlete":{"displayName":"Unranked QB"}},\n                    {"rank":2,"athlete":{"displayName":"Backup QB"}}]}]}]}\n    assert module.extract_qbs(unranked)==[]\n    assert module.extract_qbs({"depthchart":[]})==[]
    print("PASS: QB1 depth chart candidate extraction; never confirms game starter")

if __name__=="__main__":main()
