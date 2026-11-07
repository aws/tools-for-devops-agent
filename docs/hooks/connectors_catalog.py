"""
MkDocs hook: generates the Connectors catalog from connectors/.

At build time this reads connectors/*/connector.yaml and connectors/releases.yaml
and writes:

- docs/javascripts/connectors-data.json, which the JS renders as cards on the
  Connectors page and in the Partner-hosted section of the MCP Servers page;
- docs/connectors/<name>.md, one page per connector, built from its README.md;
- docs/assets/connectors/<name>/logo.svg, and logo-dark.svg when the connector
  has one, which the site shows in its dark scheme.

Which version the site shows
----------------------------
releases.yaml names, per connector, the version production serves. A connector
with an entry is shown at that version from the moment the promotion pull
request merges, which can be a few days before the last production region serves
it. When this checkout carries a different version of the connector (a newer
one waiting for promotion, say), its files are read from the newest commit on
the first-parent history of HEAD whose connector.yaml carries the production
version. Every published file change raises the version, so that commit holds
the files production serves. Searching history needs the full clone, which is
why the docs workflows check out with fetch-depth: 0.

A connector without an entry isn't served yet. It is shown from this checkout
and labelled Coming Soon. A connector whose shown version sets deprecated: true
is left out, as the console's gallery leaves it out.
"""

from __future__ import annotations

import html
import json
import logging
import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger("mkdocs.hooks.connectors_catalog")

REPO_URL = "https://github.com/aws/tools-for-devops-agent"
RAW_URL = "https://raw.githubusercontent.com/aws/tools-for-devops-agent"

# Display labels for connector.yaml's enums. tests/test_connectors_catalog.py
# keeps these in step with connectors/schema/v1/connector.schema.json.
CATEGORY_LABELS = {
    "cloud": "Cloud",
    "telemetry": "Telemetry",
    "pipeline": "Pipeline",
    "communication": "Communication",
    "devops": "DevOps",
}
TIER_LABELS = {
    "aws-managed": "AWS-managed",
    "partner-managed": "Partner-managed",
}

AVAILABLE = "available"
COMING_SOON = "coming-soon"

# The ref the GitHub links use for files read from this checkout.
CHECKOUT_REF = "main"

# connectors/schema/v1 capabilityName. Names become paths under docs/, so
# anything else is skipped rather than written.
_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LINK = re.compile(r'(!?)\[([^\]]*)\]\(\s*([^)\s]+)((?:\s+"[^"]*")?)\s*\)')
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

_GITHUB_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" '
    'style="vertical-align: text-bottom; margin-right: 0.3rem;">'
    '<path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59'
    '.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48'
    '-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33'
    '.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2'
    '-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 '
    '1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07'
    '-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55'
    '.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
)


class CatalogError(Exception):
    """releases.yaml names a connector version the site can't show."""


@dataclass
class Connector:
    """One connector at the version the site shows."""

    name: str
    meta: dict
    status: str
    ref: str
    readme: str
    logo: bytes | None
    logo_dark: bytes | None

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.name)

    @property
    def logo_path(self) -> str | None:
        return f"assets/connectors/{self.name}/logo.svg" if self.logo is not None else None

    @property
    def logo_dark_path(self) -> str | None:
        return f"assets/connectors/{self.name}/logo-dark.svg" if self.logo_dark is not None else None

    def to_json(self) -> dict:
        tier = str(self.meta.get("tier", ""))
        return {
            "id": self.name,
            "title": self.title,
            "vendor": str(self.meta.get("vendor", "")),
            "description": str(self.meta.get("description", "")),
            "version": str(self.meta.get("version", "")),
            "status": self.status,
            "tier": tier,
            "tier_label": TIER_LABELS.get(tier, tier),
            "categories": [CATEGORY_LABELS.get(c, str(c)) for c in self.meta.get("categories") or []],
            "skills": [str(s) for s in self.meta.get("skills") or []],
            "logo": self.logo_path,
            "logo_dark": self.logo_dark_path,
        }


def on_pre_build(config, **kwargs):
    """Generate connectors-data.json, connector pages and logos before the build."""
    docs_dir = Path(config["docs_dir"])
    repo_root = docs_dir.parent
    try:
        catalog = build_catalog(repo_root)
    except CatalogError as err:
        from mkdocs.exceptions import PluginError

        raise PluginError(f"Connectors catalog: {err}") from err

    _write_if_changed(
        docs_dir / "javascripts" / "connectors-data.json",
        json.dumps([c.to_json() for c in catalog], indent=2).encode("utf-8"),
    )

    for connector in catalog:
        assets = docs_dir / "assets" / "connectors" / connector.name
        if connector.logo is not None:
            _write_if_changed(assets / "logo.svg", connector.logo)
        dark = assets / "logo-dark.svg"
        if connector.logo_dark is not None:
            _write_if_changed(dark, connector.logo_dark)
        elif dark.is_file():
            dark.unlink()  # left by an earlier build, before the logo was removed
        page = render_page(connector, repo_root)
        _write_if_changed(docs_dir / "connectors" / f"{connector.name}.md", page.encode("utf-8"))

    _update_nav(config, catalog)


# --- Building the catalog ---


def build_catalog(repo_root: Path) -> list[Connector]:
    """Every connector the site shows, available ones first, each group by title."""
    connectors_dir = Path(repo_root) / "connectors"
    if not connectors_dir.is_dir():
        return []

    production = read_releases(connectors_dir / "releases.yaml")
    names = {p.name for p in connectors_dir.iterdir() if (p / "connector.yaml").is_file()}
    names |= set(production)

    catalog = []
    for name in sorted(names):
        if not _NAME.match(name):
            log.warning("Connectors catalog: skipping %r, which isn't a valid connector name", name)
            continue
        if name in production:
            connector = _released(Path(repo_root), name, production[name])
        else:
            connector = _from_checkout(Path(repo_root), name, COMING_SOON)
        if connector is None or connector.meta.get("deprecated") is True:
            continue
        catalog.append(connector)

    catalog.sort(key=lambda c: (c.status != AVAILABLE, c.title.casefold()))
    return catalog


def read_releases(path: Path) -> dict[str, str]:
    """Map each connector in releases.yaml to the version production serves."""
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as err:
        raise CatalogError(f"{path.name} can't be read: {err}") from err
    entries = data.get("connectors") if isinstance(data, dict) else None
    if entries is None:
        return {}
    if not isinstance(entries, list):
        raise CatalogError(f"{path.name}: connectors must be a list")
    production = {}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name") or not entry.get("production"):
            raise CatalogError(f"{path.name}: every entry needs a name and a production version, found {entry!r}")
        production[str(entry["name"])] = str(entry["production"])
    return production


def _released(repo_root: Path, name: str, version: str) -> Connector | None:
    """The connector at the version production serves."""
    checkout = _from_checkout(repo_root, name, AVAILABLE)
    if checkout is not None and str(checkout.meta.get("version")) == version:
        return checkout
    commit = _commit_carrying(repo_root, name, version)
    return _from_commit(repo_root, name, commit)


def _from_checkout(repo_root: Path, name: str, status: str) -> Connector | None:
    directory = repo_root / "connectors" / name
    manifest = directory / "connector.yaml"
    if not manifest.is_file():
        return None
    meta = _parse_manifest(manifest.read_text(encoding="utf-8"), f"connectors/{name}/connector.yaml")
    if meta is None:
        return None
    readme = directory / "README.md"
    return Connector(
        name=name,
        meta=meta,
        status=status,
        ref=CHECKOUT_REF,
        readme=readme.read_text(encoding="utf-8") if readme.is_file() else "",
        logo=_read_bytes(directory / "logo.svg"),
        logo_dark=_read_bytes(directory / "logo-dark.svg"),
    )


def _from_commit(repo_root: Path, name: str, commit: str) -> Connector:
    prefix = f"connectors/{name}"
    meta = _parse_manifest(_git_blob(repo_root, commit, f"{prefix}/connector.yaml").decode("utf-8"), prefix)
    readme = _git_blob(repo_root, commit, f"{prefix}/README.md")
    return Connector(
        name=name,
        meta=meta or {},
        status=AVAILABLE,
        ref=commit,
        readme=readme.decode("utf-8") if readme is not None else "",
        logo=_git_blob(repo_root, commit, f"{prefix}/logo.svg"),
        logo_dark=_git_blob(repo_root, commit, f"{prefix}/logo-dark.svg"),
    )


def _commit_carrying(repo_root: Path, name: str, version: str) -> str:
    """The newest first-parent commit whose connectors/<name>/connector.yaml carries version."""
    prefix = f"connectors/{name}"
    commits = _git(repo_root, "rev-list", "--first-parent", "HEAD", "--", prefix).split()
    for commit in commits:
        blob = _git_blob(repo_root, commit, f"{prefix}/connector.yaml")
        if blob is None:
            continue  # the commit removed the connector
        meta = _parse_manifest(blob.decode("utf-8", errors="replace"), None)
        if meta is not None and str(meta.get("version")) == version:
            return commit

    if _git(repo_root, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise CatalogError(
            f"releases.yaml serves {name} {version}, which this checkout doesn't carry, "
            "and the clone is shallow so its history can't be searched. "
            "Check out with fetch-depth: 0 (or run git fetch --unshallow)."
        )
    raise CatalogError(
        f"releases.yaml serves {name} {version}, but no commit on the first-parent "
        f"history of HEAD has {prefix}/connector.yaml at that version"
    )


def _parse_manifest(text: str, label: str | None) -> dict | None:
    try:
        meta = yaml.safe_load(text)
    except yaml.YAMLError as err:
        if label:
            log.warning("Connectors catalog: skipping %s, which can't be read: %s", label, err)
        return None
    if not isinstance(meta, dict):
        if label:
            log.warning("Connectors catalog: skipping %s, which isn't a mapping", label)
        return None
    return meta


def _git(repo_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError as err:
        raise CatalogError("git isn't installed, and it's needed to read released connectors from history") from err
    if result.returncode != 0:
        raise CatalogError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _git_blob(repo_root: Path, commit: str, path: str) -> bytes | None:
    """A file's content at commit, or None if the commit doesn't have it."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "blob", f"{commit}:{path}"],
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _read_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


# --- Rendering a connector page ---


def render_page(connector: Connector, repo_root: Path) -> str:
    """The connector's docs page: a header built from connector.yaml, then its README."""
    meta = connector.meta
    title = html.escape(connector.title)
    parts = [f"# {title}\n"]

    if connector.logo_path:
        logo = f"../{connector.logo_path}"
        alt = f"{title} logo"
        if connector.logo_dark_path:
            parts.append(
                f"![{alt}]({logo}#only-light){{ .connector-page-logo }}"
                f"![{alt}](../{connector.logo_dark_path}#only-dark){{ .connector-page-logo }}\n"
            )
        else:
            parts.append(f"![{alt}]({logo}){{ .connector-page-logo }}\n")

    if connector.status == COMING_SOON:
        parts.append(
            '!!! info "Coming Soon"\n\n'
            "    This connector isn't available in the AWS DevOps Agent console yet.\n"
        )

    description = str(meta.get("description", "")).strip()
    if description:
        parts.append(f"{html.escape(description)}\n")

    parts.append(
        f'<a href="{REPO_URL}/tree/{connector.ref}/connectors/{connector.name}" '
        f'target="_blank" rel="noopener" class="md-button">{_GITHUB_ICON}View on GitHub</a>\n'
    )
    parts.append(_meta_block(connector))

    body = transform_readme(connector.readme, connector.name, connector.ref)
    if body.strip():
        parts.append(body)
    skills = _skills_section(connector, Path(repo_root))
    if skills:
        parts.append(skills)
    return "\n".join(parts)


def _meta_block(connector: Connector) -> str:
    data = connector.to_json()
    byline = [f'by <strong>{html.escape(data["vendor"])}</strong>'] if data["vendor"] else []
    if data["version"]:
        byline.append(f'version {html.escape(data["version"])}')

    tags = []
    if connector.status == COMING_SOON:
        tags.append('<span class="tag tag-coming-soon">Coming Soon</span>')
    if data["tier_label"]:
        tags.append(f'<span class="tag tag-tier">{html.escape(data["tier_label"])}</span>')
    tags += [f'<span class="tag tag-category">{html.escape(c)}</span>' for c in data["categories"]]

    links = []
    for label, key in (("Documentation", "docs_url"), ("Support", "support_url")):
        url = str(connector.meta.get(key) or "")
        if url.startswith("https://"):
            links.append(f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{label}</a>')

    lines = ['<div class="skill-page-meta connector-page-meta">']
    if byline:
        lines.append(f'<div class="skill-meta"><span class="skill-author">{" · ".join(byline)}</span></div>')
    if tags:
        lines.append(f'<div class="skill-tags">{" ".join(tags)}</div>')
    if links:
        lines.append(f'<div class="connector-links">{" · ".join(links)}</div>')
    lines.append("</div>\n")
    return "\n".join(lines)


def _skills_section(connector: Connector, repo_root: Path) -> str:
    """The skills the console offers with the connector, linked when the skill has a page."""
    skills = [str(s) for s in connector.meta.get("skills") or []]
    if not skills:
        return ""
    lines = ["## Skills", "", "The console offers to install these skills when you add this connector:", ""]
    for skill in skills:
        if _NAME.match(skill) and (repo_root / "skills" / skill / "SKILL.md").is_file():
            lines.append(f"- [`{skill}`](../skills/{skill}.md)")
        else:
            lines.append(f"- `{skill}`")
    return "\n".join(lines) + "\n"


def transform_readme(readme: str, name: str, ref: str) -> str:
    """Drop the README's leading title, since the page has one, and point relative links at GitHub.

    The site renders the README away from connectors/<name>/, so a relative link
    that works on GitHub fails mkdocs build --strict. Fenced code is left as is.
    """
    out = []
    fence = None
    started = False
    for line in readme.split("\n"):
        match = _FENCE.match(line)
        if fence:
            out.append(line)
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            continue
        if match:
            fence = match.group(1)
            started = True
            out.append(line)
            continue
        if not started:
            if not line.strip():
                continue
            started = True
            if line.startswith("# "):
                continue
        out.append(_rewrite_links(line, name, ref))
    return "\n".join(out).strip("\n") + "\n"


def _rewrite_links(line: str, name: str, ref: str) -> str:
    def absolute(match: re.Match) -> str:
        bang, text, target, title = match.groups()
        if _SCHEME.match(target) or target.startswith(("#", "/")):
            return match.group(0)
        path, _, fragment = target.partition("#")
        resolved = posixpath.normpath(posixpath.join("connectors", name, path))
        if resolved == ".." or resolved.startswith("../"):
            return match.group(0)
        if bang:
            url = f"{RAW_URL}/{ref}/{resolved}"
        else:
            url = f"{REPO_URL}/blob/{ref}/{resolved}" + (f"#{fragment}" if fragment else "")
        return f"{bang}[{text}]({url}{title})"

    return _LINK.sub(absolute, line)


# --- Writing ---


def _write_if_changed(path: Path, content: bytes) -> None:
    """Write only on change, so mkdocs serve's file watcher doesn't loop."""
    if path.is_file() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _update_nav(config, catalog: list[Connector]) -> None:
    """Append connector pages to Connectors > Catalog in the nav, in memory."""
    for item in config.get("nav") or []:
        if not (isinstance(item, dict) and "Connectors" in item):
            continue
        for entry in item["Connectors"]:
            if not (isinstance(entry, dict) and "Catalog" in entry):
                continue
            catalog_nav = entry["Catalog"]
            existing = set()
            for sub in catalog_nav:
                existing.update(sub.values() if isinstance(sub, dict) else [sub])
            for connector in catalog:
                page = f"connectors/{connector.name}.md"
                if page not in existing:
                    catalog_nav.append({connector.title: page})
            return
