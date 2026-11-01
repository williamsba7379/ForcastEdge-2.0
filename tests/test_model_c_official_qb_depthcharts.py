#!/usr/bin/env python3
"""Offline fixtures for official depth-chart adapter; no network or production writes."""
import importlib.util
import pathlib
root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("official_qb", root / "scripts/model_c_official_qb_depthcharts.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
def table(header="Position", first="1st", player="Fixture Quarterback"):
    return f"<html><table><tr><th>{header}</th><th>{first}</th><th>2nd</th></tr><tr><td>RB</td><td>Other Player</td><td>Backup</td></tr><tr><td>QB</td><td>{player}</td><td>Backup</td></tr></table></html>"
assert mod.extract_first_string_qb(table()) == "Fixture Quarterback"
assert mod.extract_first_string_qb(table(header="POS")) == "Fixture Quarterback"
for html in (table(first="Starter"), table(player=""), table(player="—"),
             table()+table(), "<html><table><tr><td>QB</td><td>Fixture Quarterback</td></tr></table></html>"):
    try:
        mod.extract_first_string_qb(html)
    except ValueError:
        pass
    else:
        raise AssertionError("Unverified or ambiguous QB accepted")
assert set(mod.SOURCES) == {"SF", "BAL"}
print("PASS: official first-string QB fixtures and fail-closed cases")
