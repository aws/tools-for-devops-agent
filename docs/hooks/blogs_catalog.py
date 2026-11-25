"""
MkDocs hook: renders the Blogs page from docs/blogs/posts.json.

At build time:
- Checks docs/blogs/posts.json and docs/blogs/tags.json. An error stops the
  build, so `mkdocs build --strict` in CI catches a bad entry before it merges.
- Replaces the <!-- blog-posts --> marker in docs/blogs/index.md with one
  section per format (written, video, audio), newest post first.

The posts are static HTML, so the list works without JavaScript and the site
search indexes it. docs/javascripts/blogs.js adds the search and filters.
"""

import datetime
import html
import json
import re
from pathlib import Path

try:
    from mkdocs.exceptions import PluginError
except ImportError:  # the unit tests run without mkdocs installed
    class PluginError(Exception):
        pass

PAGE = "blogs/index.md"
MARKER = "<!-- blog-posts -->"
FORMATS = [("written", "Written"), ("video", "Video"), ("audio", "Audio")]
REQUIRED = {
    "title": str, "url": str, "authors": list, "date": str, "source": str,
    "official": bool, "format": str, "description": str, "tags": list,
}
URL_RE = re.compile(r"^https://[^\s\"'<>]+$")

_posts: list = []


def on_pre_build(config, **kwargs):
    global _posts
    blogs_dir = Path(config["docs_dir"]) / "blogs"
    tags = _load_tags(blogs_dir / "tags.json")
    _posts = _load_posts(blogs_dir / "posts.json", tags)


def on_page_markdown(markdown, page, config, files, **kwargs):
    if page.file.src_uri != PAGE:
        return markdown
    if MARKER not in markdown:
        raise PluginError(f"{PAGE} must contain {MARKER}")
    return markdown.replace(MARKER, _render(_posts))


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PluginError(f"{path}: {e}") from e


def _load_tags(path: Path) -> set:
    data = _load_json(path)
    names, aliases = set(), set()
    for t in data.get("tags", []):
        name = t.get("name")
        if not isinstance(name, str) or not name:
            raise PluginError(f"{path}: every tag needs a name")
        if name in names:
            raise PluginError(f"{path}: tag '{name}' is listed twice")
        names.add(name)
        for a in t.get("aliases", []):
            if a in aliases:
                raise PluginError(f"{path}: alias '{a}' belongs to two tags")
            aliases.add(a)
    return names


def _load_posts(path: Path, tags: set) -> list:
    data = _load_json(path)
    if not isinstance(data, list):
        raise PluginError(f"{path}: must be a JSON array of posts")
    errors, urls = [], set()
    for i, p in enumerate(data):
        where = f"{path.name} entry {i} ({p.get('url', 'no url') if isinstance(p, dict) else '?'})"
        if not isinstance(p, dict):
            errors.append(f"{where}: must be an object")
            continue
        for key, kind in REQUIRED.items():
            if not isinstance(p.get(key), kind):
                errors.append(f"{where}: '{key}' must be a {kind.__name__}")
        if errors and errors[-1].startswith(where):
            continue
        if not URL_RE.match(p["url"]):
            errors.append(f"{where}: url must be an https:// link")
        if p["url"] in urls:
            errors.append(f"{where}: url is listed twice")
        urls.add(p["url"])
        try:
            datetime.date.fromisoformat(p["date"])
        except ValueError:
            errors.append(f"{where}: date must be YYYY-MM-DD")
        if p["format"] not in dict(FORMATS):
            errors.append(f"{where}: format must be one of {', '.join(dict(FORMATS))}")
        if not p["authors"] or not all(isinstance(a, str) and a for a in p["authors"]):
            errors.append(f"{where}: authors must list at least one name")
        if not p["title"].strip() or not p["description"].strip():
            errors.append(f"{where}: title and description must not be empty")
        if not p["tags"]:
            errors.append(f"{where}: add at least one tag")
        unknown = [t for t in p["tags"] if t not in tags]
        if unknown:
            errors.append(f"{where}: tags not in tags.json: {', '.join(map(str, unknown))}")
    if errors:
        raise PluginError("Blog posts are not valid:\n  " + "\n  ".join(errors))
    return sorted(data, key=lambda p: (p["date"], p["title"]), reverse=True)


def _render(posts: list) -> str:
    out = []
    for fmt, heading in FORMATS:
        items = [p for p in posts if p["format"] == fmt]
        if not items:
            continue
        out.append(f"## {heading} {{ #{fmt} }}\n")
        out.append(f'<div class="skill-group blog-list" data-format="{fmt}">')
        out.extend(_render_post(p) for p in items)
        out.append("</div>\n")
    return "\n".join(out)


def _render_post(p: dict) -> str:
    e = lambda s: html.escape(s, quote=True)  # noqa: E731
    day = datetime.date.fromisoformat(p["date"])
    kind = "aws" if p["official"] else "community"
    badge = (
        '<span class="tag tag-service">AWS</span>' if p["official"]
        else '<span class="tag tag-agent">Community</span>'
    )
    tags = " ".join(
        f'<button type="button" class="tag tag-domain blog-tag" data-tag="{e(t)}">{e(t)}</button>'
        for t in p["tags"]
    )
    # The card reuses the catalog classes in stylesheets/extra.css (skill-card,
    # skill-meta, skill-author, skill-tags, tag-*), so posts look like catalog entries.
    return (
        f'<article class="skill-card blog-post" data-date="{e(p["date"])}" data-kind="{kind}" '
        f'data-source="{e(p["source"])}" data-tags="{e("|".join(p["tags"]))}">'
        f'<p class="blog-post-title"><a href="{e(p["url"])}" target="_blank" rel="noopener">{e(p["title"])}</a></p>'
        f'<div class="skill-meta">{badge} <span class="skill-author">'
        f'<time datetime="{e(p["date"])}">{day.day} {day:%b %Y}</time>'
        f' · {e(", ".join(p["authors"]))} · {e(p["source"])}</span></div>'
        f'<p>{e(p["description"])}</p>'
        f'<div class="skill-tags">{tags}</div>'
        "</article>"
    )
