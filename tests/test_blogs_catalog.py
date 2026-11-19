"""Unit tests for docs/hooks/blogs_catalog.py, the hook that renders the Blogs page.

The hook checks docs/blogs/posts.json against docs/blogs/tags.json and stops the
site build on a bad entry. These tests check the real data files and the checks
themselves, and that text from a post is escaped in the page. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOGS = ROOT / "docs" / "blogs"
HOOK = ROOT / "docs" / "hooks" / "blogs_catalog.py"

GOOD = {
    "title": "A post",
    "url": "https://example.com/post",
    "authors": ["An Author"],
    "date": "2026-01-02",
    "source": "Example",
    "official": False,
    "format": "written",
    "description": "What the post shows.",
    "tags": ["Investigations"],
}


def _load_hook():
    """Import the hook by path, since docs/hooks isn't a package."""
    spec = importlib.util.spec_from_file_location("blogs_catalog", HOOK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


class DataFileTests(unittest.TestCase):
    """The committed posts.json and tags.json pass the hook's checks."""

    def test_posts_are_valid(self):
        tags = hook._load_tags(BLOGS / "tags.json")
        posts = hook._load_posts(BLOGS / "posts.json", tags)
        self.assertGreater(len(posts), 0)

    def test_every_tag_is_used(self):
        tags = hook._load_tags(BLOGS / "tags.json")
        posts = json.loads((BLOGS / "posts.json").read_text(encoding="utf-8"))
        used = {t for p in posts for t in p["tags"]}
        self.assertEqual(sorted(tags - used), [], "remove unused tags from tags.json")


class CheckTests(unittest.TestCase):
    """Each check rejects the entry it is meant to reject."""

    tags = {"Investigations"}

    def _load(self, posts):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "posts.json"
            path.write_text(json.dumps(posts), encoding="utf-8")
            return hook._load_posts(path, self.tags)

    def _rejects(self, **changes):
        post = copy.deepcopy(GOOD)
        post.update(changes)
        with self.assertRaises(hook.PluginError):
            self._load([post])

    def test_accepts_a_good_post(self):
        self.assertEqual(len(self._load([GOOD])), 1)

    def test_rejects_an_unknown_tag(self):
        self._rejects(tags=["investigations"])

    def test_rejects_no_tags(self):
        self._rejects(tags=[])

    def test_rejects_a_non_https_url(self):
        self._rejects(url="http://example.com/post")
        self._rejects(url="javascript:alert(1)")

    def test_rejects_a_bad_date(self):
        self._rejects(date="2026-13-01")

    def test_rejects_an_unknown_format(self):
        self._rejects(format="podcast")

    def test_rejects_a_missing_field(self):
        post = copy.deepcopy(GOOD)
        del post["description"]
        with self.assertRaises(hook.PluginError):
            self._load([post])

    def test_rejects_a_duplicate_url(self):
        with self.assertRaises(hook.PluginError):
            self._load([GOOD, GOOD])

    def test_sorts_newest_first(self):
        older = dict(GOOD, url="https://example.com/older", date="2025-12-01")
        self.assertEqual([p["date"] for p in self._load([older, GOOD])], ["2026-01-02", "2025-12-01"])


class RenderTests(unittest.TestCase):
    def test_escapes_post_text(self):
        post = dict(GOOD, title='<script>alert("x")</script>', authors=['A "quoted" name'])
        out = hook._render([post])
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("A &quot;quoted&quot; name", out)

    def test_skips_formats_with_no_posts(self):
        out = hook._render([GOOD])
        self.assertIn("## Written", out)
        self.assertNotIn("## Video", out)


if __name__ == "__main__":
    unittest.main()
