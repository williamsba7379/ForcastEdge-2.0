"""Strict offline structural checks for the isolated manual workflow.

No external packages, network, workflow dispatch, or production changes.
"""
from pathlib import Path
import re
import unittest

PATH=Path(".github/workflows/nfl-ab-wednesday-evidence-rehearsal.yml")

def strict_mapping_keys(text):
    """Detect duplicate mapping keys, respecting YAML list items and block scalars."""
    contexts=[(-1,{},set())]
    scalar_indent=None
    item_index=0
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
        is_item=bool(re.match(r"^\s*- ",line))
        effective_indent=indent+2 if is_item else indent
        while len(contexts)>1 and contexts[-1][0]>=effective_indent:
            contexts.pop()
        if is_item:
            item_index+=1
            contexts.append((indent+1,{},set()))
        m=re.match(r"^\s*(?:- )?([A-Za-z_][A-Za-z_0-9-]*):(?:\s|$)",line)
        if m:
            key=m.group(1)
            parent=contexts[-1]
            if key in parent[2]:
                raise ValueError("DUPLICATE_YAML_KEY")
            parent[2].add(key)
            contexts.append((effective_indent,{},set()))
            if line.rstrip().endswith(("|",">")):
                scalar_indent=indent

class WorkflowYamlTests(unittest.TestCase):
    def test_workflow_structure_and_safety(self):
        text=PATH.read_text()
        strict_mapping_keys(text)
        for label in ("Download and verify exact capture archive and extracted bytes","Review original capture","Upload research-only review","Verify exact capture run"):
            self.assertEqual(text.count("- name: "+label),1)
        for required in ("validate_capture_run(", "validate_artifact_expiry(", "validate_review_manifest(", "capture_commit_sha:", "reviewed_games_sha256:", "retention-days: 30", "contents: read", "actions: read"):
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
