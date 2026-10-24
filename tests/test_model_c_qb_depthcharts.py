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
    alternate={"depthcharts":{"offense":{"positions":[{"position":"QB","athletes":[{"slot":1,"athlete":{"displayName":"Alternate QB"}},{"slot":2,"athlete":{"displayName":"Backup QB"}}]}]}}}
    assert module.extract_qbs(alternate)==["Alternate QB"]
    live_shape={"depthchart":[{"name":"3WR 1TE","positions":{"qb":{"position":{"abbreviation":"QB"},"athletes":[{"displayName":"Listed QB1"},{"displayName":"Listed QB2"}]}}}]}
    assert module.extract_qbs(live_shape)==["Listed QB1"]
    assert module.extract_qbs({"depthchart":[]})==[]
    print("PASS: QB1 depth chart candidate extraction; never confirms game starter")

if __name__=="__main__":main()
