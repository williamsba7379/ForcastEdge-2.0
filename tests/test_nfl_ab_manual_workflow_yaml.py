"""Strict offline structural checks for the isolated manual workflow.

No external packages, network, workflow dispatch, or production changes.
"""
from pathlib import Path
import re
import unittest

PATH=Path(".github/workflows/nfl-ab-wednesday-evidence-rehearsal.yml")

def validate_workflow(text):
    # Fail on malformed indentation, duplicate YAML mapping keys at the same level,
    # and duplicate review-stage actions. Block scalar bodies are intentionally skipped.
    stack=[]
    scalar_indent=None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent=len(line)-len(line.lstrip(" "))
        if "\t" in line[:indent] or indent%2:
            raise ValueError("INVALID_YAML_INDENT")
        if scalar_indent is not None:
            if indent>scalar_indent:
                continue
            scalar_indent=None
        while stack and indent<=stack[-1][0]:
            stack.pop()
        match=re.match(r"^\s*(?:- )?([A-Za-z_][A-Za-z_0-9-]*):(?:\s|$)",line)
        if match:
            key=match.group(1)
            parent=stack[-1][1] if stack else "root"
            # Each list item is a distinct mapping; reset its key set at the dash.
            if re.match(r"^\s*- ",line):
                parent+=f"/item-{len(line)}-{line.strip()}"
            identity=(indent,parent,key)
            if identity in seen:
                raise ValueError("DUPLICATE_YAML_KEY")
            seen.add(identity)
            stack.append((indent,parent+"/"+key))
            if line.rstrip().endswith("|") or line.rstrip().endswith(">"):
                scalar_indent=indent
    for label in ("Download existing raw evidence","Review original capture","Upload research-only review","Verify exact capture run"):
        if text.count("- name: "+label)!=1:
            raise ValueError("MISSING_OR_DUPLICATE_REVIEW_STEP")
    for required in ("validate_capture_run(", "validate_capture_artifact(", "validate_review_manifest(", "capture_commit_sha:", "reviewed_games_sha256:", "retention-days: 30", "contents: read", "actions: read"):
        if required not in text:
            raise ValueError("MISSING_SAFETY_GATE")
    return True

# Correctly track duplicate keys per mapping and YAML sequence item.
def strict_mapping_keys(text):
    mappings=[(-1,set())]
    scalar_indent=None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent=len(line)-len(line.lstrip(" "))
        if "\t" in line[:indent] or indent%2:
            raise ValueError("INVALID_YAML_INDENT")
        if scalar_indent is not None:
            if indent>scalar_indent:
                continue
            scalar_indent=None
        while mappings[-1][0]>=indent:
            mappings.pop()
        if re.match(r"^\s*- ",line):
            mappings.append((indent,set()))
        m=re.match(r"^\s*(?:- )?([A-Za-z_][A-Za-z_0-9-]*):(?:\s|$)",line)
        if m:
            key=m.group(1)
            if key in mappings[-1][1]:
                raise ValueError("DUPLICATE_YAML_KEY")
            mappings[-1][1].add(key)
            mappings.append((indent,set()))
            if line.rstrip().endswith(("|",">")):
                scalar_indent=indent

class WorkflowYamlTests(unittest.TestCase):
    def test_workflow_structure_and_safety(self):
        text=PATH.read_text()
        strict_mapping_keys(text)
        for label in ("Download existing raw evidence","Review original capture","Upload research-only review","Verify exact capture run"):
            self.assertEqual(text.count("- name: "+label),1)
        for required in ("validate_capture_run(", "validate_capture_artifact(", "validate_review_manifest(", "capture_commit_sha:", "reviewed_games_sha256:", "retention-days: 30", "contents: read", "actions: read"):
            self.assertIn(required,text)
    def test_duplicate_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_YAML_KEY"):
            strict_mapping_keys("root:\n  env:\n    A: one\n  env:\n    B: two\n")
    def test_duplicate_run_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_YAML_KEY"):
            strict_mapping_keys("steps:\n  - name: Verify\n    run: |\n      echo ok\n    run: |\n      echo again\n")
    def test_scalar_contents_not_treated_as_yaml(self):
        strict_mapping_keys("steps:\n  - name: Verify\n    run: |\n      echo 'env: something'\n      echo 'run: again'\n")
if __name__=="__main__":
    unittest.main()
