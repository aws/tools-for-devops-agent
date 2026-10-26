"""Unit tests for docs/hooks/skills_catalog.py, the GitHub Pages catalog hook.

The hook renders metadata.aws-devops-agent-skills.agent-types, which carries the
API values, as readable labels. That label map is a second list of the agent
types, so these tests keep it in step with agent-types.json: a value added there
without a label would show the raw API value in the catalog. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / ".github" / "scripts" / "skill-rules"
HOOK = ROOT / "docs" / "hooks" / "skills_catalog.py"


def _load_hook():
    """Import the hook by path, since docs/hooks isn't a package."""
    spec = importlib.util.spec_from_file_location("skills_catalog", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent_types() -> list[str]:
    return json.loads((RULES_DIR / "agent-types.json").read_text(encoding="utf-8"))["values"]


class AgentTypeLabelTests(unittest.TestCase):
    """AGENT_TYPE_LABELS and agent-types.json must list the same agent types."""

    def setUp(self):
        self.labels = _load_hook().AGENT_TYPE_LABELS
        self.values = _agent_types()

    def test_every_agent_type_has_a_label(self):
        missing = [v for v in self.values if v not in self.labels]
        self.assertEqual(
            missing,
            [],
            f"these would show as raw API values in the catalog; add a label in "
            f"{HOOK.relative_to(ROOT)}: {missing}",
        )

    def test_every_label_names_a_real_agent_type(self):
        unknown = [v for v in self.labels if v not in self.values]
        self.assertEqual(
            unknown,
            [],
            f"labels for values that aren't in agent-types.json, so they can never be shown: {unknown}",
        )

    def test_labels_are_non_empty_single_line_text(self):
        for value, label in self.labels.items():
            with self.subTest(value=value):
                self.assertIsInstance(label, str)
                self.assertTrue(label.strip(), "label is empty")
                self.assertEqual(label, label.strip(), "label has surrounding whitespace")
                self.assertNotIn("\n", label)


class DimensionRenderingTests(unittest.TestCase):
    """Every skill in the repository renders a label, never a raw API value."""

    def setUp(self):
        self.hook = _load_hook()

    def test_agent_types_are_rendered_as_labels(self):
        catalog = self.hook._build_catalog(str(ROOT))
        self.assertTrue(catalog, "the catalog is empty, so nothing was checked")
        labels = set(self.hook.AGENT_TYPE_LABELS.values())
        api_values = set(self.hook.AGENT_TYPE_LABELS)
        for skill in catalog:
            with self.subTest(skill=skill["id"]):
                rendered = skill["dimensions"].get("agent-types", [])
                self.assertTrue(rendered, "no agent types rendered")
                for shown in rendered:
                    self.assertIn(shown, labels, f"{shown!r} is not a known label")
                    self.assertNotIn(shown, api_values, f"the raw API value {shown!r} reached the catalog")


if __name__ == "__main__":
    unittest.main()
