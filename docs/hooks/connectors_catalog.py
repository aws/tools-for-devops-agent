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

Partner READMEs
---------------
A README is written by the partner, and Markdown passes raw HTML through, so a
connector page's HTML is sanitised after Markdown has rendered it (on_page_content)
rather than its source being scanned: only the tags, attributes and URL schemes
in SAFE_TAGS, SAFE_ATTRIBUTES and SAFE_URL_SCHEMES survive. Checking the rendered
HTML means nothing here has to agree with the Markdown parser about what is code.
The build fails when sanitising removed anything, naming it, and the sanitised
HTML is what is published either way. Sanitising needs nh3, which the docs
workflows install; a build without it stops rather than publish unsanitised pages.

Two rules beyond the allowlists:

- An id or name starting with "__" is removed. That prefix is Material's own
  (__config, __search, __toc, ...), and its client looks some of those up by id,
  taking the first match in the page; the README comes first, so a README
  <div id="__config"> would replace the theme's configuration. The code
  highlighter's __codelineno- line anchors are the exception.
- A placeholder such as <WEBHOOK_URL> or <YOUR TOKEN>, which Markdown passes
  through as a tag, is shown as text, as GitHub shows it, instead of failing
  the build. That applies to a tag whose name no HTML, SVG or MathML element
  has and which carries no attribute values; a real element is still removed.

Partner logos
-------------
A logo is shown with <img>, where an SVG can't run script, but it is also served
from the site as a file, and an SVG opened directly is a document whose scripts
run in the site's origin. So the build fails on a logo that holds anything but
drawing markup: an element outside LOGO_ELEMENTS, an attribute outside
LOGO_ATTRIBUTES (event handlers included), a reference (href, url()) to anything
but an id in the same file, CSS that can fetch or run something (_CSS_RISKY,
which refuses a backslash because CSS escapes can spell url( and @import past a
regex), a DOCTYPE or entity, or a processing instruction. Each logo is checked
at the version the site shows.
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

from collections import Counter
from html.parser import HTMLParser
from xml.etree import ElementTree

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

# What a connector page may contain once rendered: what Markdown and the site's
# extensions (tables, admonitions, code highlighting, emoji) produce, and the
# page header this hook writes. Anything else is removed and fails the build;
# add to these only for markup that can't run script.
SAFE_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "dd", "del", "details", "div", "dl", "dt",
    "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li", "mark",
    "ol", "p", "path", "pre", "s", "small", "span", "strong", "sub", "summary", "sup", "svg",
    "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}
SAFE_ATTRIBUTES = {
    "*": {"class", "id", "title"},
    "a": {"href", "name", "rel", "target"},
    "img": {"alt", "height", "loading", "src", "width"},
    "ol": {"start"},
    "details": {"open"},
    "td": {"align", "colspan", "rowspan", "style"},
    "th": {"align", "colspan", "rowspan", "style"},
    # Inline icons: the GitHub button here, and emoji
    "svg": {"aria-hidden", "height", "viewBox", "width", "xmlns"},
    "path": {"d", "fill"},
}
# Relative URLs are kept, so links within the site work.
SAFE_URL_SCHEMES = {"http", "https", "mailto"}
# Markdown tables align columns with style="text-align: ..."
SAFE_STYLE_PROPERTIES = {"text-align"}

# Material's element ids start with "__"; an author id or name may not. Code
# blocks with line numbers get __codelineno- anchors, which Material never
# looks up.
_RESERVED_ID = re.compile(r"^__(?!codelineno-)")

# Every HTML (current and obsolete), SVG and MathML element name. A tag named
# anything else is a placeholder and becomes text. Text can't run script, so
# this list only decides whether a tag is shown as text or fails the build.
KNOWN_ELEMENTS = frozenset("""
    a abbr acronym address applet area article aside audio b base basefont bdi bdo bgsound big
    blink blockquote body br button canvas caption center cite code col colgroup data datalist
    dd del details dfn dialog dir div dl dt em embed fieldset figcaption figure font footer
    form frame frameset h1 h2 h3 h4 h5 h6 head header hgroup hr html i iframe image img input
    ins isindex kbd keygen label legend li link listing main map mark marquee menu menuitem
    meta meter multicol nav nextid nobr noembed noframes noscript object ol optgroup option
    output p param picture plaintext pre progress q rb rp rt rtc ruby s samp script search
    section select slot small source spacer span strike strong style sub summary sup table
    tbody td template textarea tfoot th thead time title tr track tt u ul var video wbr xmp
    animate animatemotion animatetransform circle clippath defs desc discard ellipse feblend
    fecolormatrix fecomponenttransfer fecomposite feconvolvematrix fediffuselighting
    fedisplacementmap fedistantlight fedropshadow feflood fefunca fefuncb fefuncg fefuncr
    fegaussianblur feimage femerge femergenode femorphology feoffset fepointlight
    fespecularlighting fespotlight fetile feturbulence filter foreignobject g line
    lineargradient marker mask metadata mpath path pattern polygon polyline radialgradient rect
    set stop svg switch symbol text textpath tspan use view
    math maction annotation annotation-xml menclose merror mfenced mfrac mi mmultiscripts mn mo
    mover mpadded mphantom mprescripts mroot mrow ms mspace msqrt mstyle msub msubsup msup
    mtable mtd mtext mtr munder munderover none semantics
""".split())

# A start or end tag whose attributes, if any, are bare words: <API_KEY>, <YOUR TOKEN>
_BARE_TAG = re.compile(r"</?([A-Za-z][A-Za-z0-9_.:-]*)((?:\s+[A-Za-z_][A-Za-z0-9_.:-]*)*)\s*/?>")

# What a logo may contain: SVG drawing elements, and presentation and geometry
# attributes. No script, foreignObject, a, image, animation or filter elements,
# and no event handlers. Add to these only markup that can neither run script
# nor fetch anything.
LOGO_ELEMENTS = {
    "circle", "clipPath", "defs", "desc", "ellipse", "g", "line", "linearGradient", "mask",
    "path", "pattern", "polygon", "polyline", "radialGradient", "rect", "stop", "style",
    "svg", "symbol", "text", "title", "tspan", "use",
}
LOGO_ATTRIBUTES = {
    "aria-hidden", "aria-label", "baseProfile", "class", "clip-path", "clip-rule",
    "clipPathUnits", "color", "cx", "cy", "d", "display", "dominant-baseline", "dx", "dy",
    "enable-background", "fill", "fill-opacity", "fill-rule", "focusable", "font-family",
    "font-size", "font-style", "font-weight", "fx", "fy", "gradientTransform",
    "gradientUnits", "height", "href", "id", "isolation", "letter-spacing", "mask",
    "maskContentUnits", "maskUnits", "mix-blend-mode", "offset", "opacity", "overflow",
    "patternContentUnits", "patternTransform", "patternUnits", "points",
    "preserveAspectRatio", "r", "role", "rx", "ry", "shape-rendering", "spreadMethod",
    "stop-color", "stop-opacity", "stroke", "stroke-dasharray", "stroke-dashoffset",
    "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-opacity",
    "stroke-width", "style", "text-anchor", "text-rendering", "transform", "type",
    "version", "viewBox", "visibility", "width", "x", "x1", "x2", "y", "y1", "y2",
}
_SVG_NS = "{http://www.w3.org/2000/svg}"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.IGNORECASE | re.DOTALL)
# CSS that can fetch or run something, beyond the url() read above. A backslash
# is refused outright because CSS lets any letter be written as an escape, so
# u\72l( and @\69mport mean url( and @import to a browser but not to a regex;
# no logo needs one. The fetching functions are named because they take a URL
# without url(). (PR #204 review)
_CSS_RISKY = (
    (re.compile(r"\\"), "a CSS escape"),
    (re.compile(r"@import", re.IGNORECASE), "@import"),
    (re.compile(r"image-set\s*\(", re.IGNORECASE), "image-set()"),
    (re.compile(r"\bsrc\s*\(", re.IGNORECASE), "src()"),
    (re.compile(r"expression\s*\(", re.IGNORECASE), "expression()"),
    (re.compile(r"javascript\s*:", re.IGNORECASE), "a javascript: URL"),
    (re.compile(r"behavior\s*:", re.IGNORECASE), "a behavior property"),
    (re.compile(r"-moz-binding", re.IGNORECASE), "-moz-binding"),
)

_GITHUB_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" '
    'class="connector-github-icon">'
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
    """A connector the site can't show: a bad releases.yaml version, or a page it won't publish."""


# Connector name -> the ref its page was built from, for on_page_content's errors.
_SHOWN_REFS: dict[str, str] = {}


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

    _SHOWN_REFS.clear()
    _SHOWN_REFS.update({c.name: c.ref for c in catalog})
    _update_nav(config, catalog)


def on_page_content(html_text, page, **kwargs):
    """Publish a connector page only as sanitised HTML, and fail the build if sanitising changed it."""
    src = page.file.src_uri
    if not src.startswith("connectors/") or src == "connectors/index.md":
        return html_text

    from mkdocs.exceptions import PluginError

    name = posixpath.splitext(posixpath.basename(src))[0]
    try:
        cleaned, removed = sanitize_html(html_text)
    except CatalogError as err:
        raise PluginError(f"Connectors catalog: {err}") from err
    if removed:
        ref = _SHOWN_REFS.get(name, CHECKOUT_REF)
        at = "" if ref == CHECKOUT_REF else f" at {ref[:12]}"
        shown = "; ".join(removed[:5]) + (f"; and {len(removed) - 5} more" if len(removed) > 5 else "")
        raise PluginError(
            f"Connectors catalog: the page for connectors/{name}/README.md{at} renders HTML the site "
            f"won't publish: {shown}. Use plain Markdown, or show it as code."
        )
    return cleaned


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
        for filename, svg in (("logo.svg", connector.logo), ("logo-dark.svg", connector.logo_dark)):
            problem = check_logo(svg) if svg is not None else None
            if problem:
                at = "" if connector.ref == CHECKOUT_REF else f" at {connector.ref[:12]}"
                raise CatalogError(
                    f"connectors/{name}/{filename}{at} has {problem}, which the site won't serve. "
                    "A logo may hold only SVG drawing elements and attributes, and references within the file."
                )
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
    started = False
    for _, line, in_code in _scan_lines(readme):
        if in_code:
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


# --- Checking a logo ---


def check_logo(svg: bytes) -> str | None:
    """What makes an SVG logo unsafe to serve as a file, or None if it holds only drawing markup."""
    try:
        text = svg.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "content that isn't UTF-8"
    # Entities can only be declared in a DOCTYPE, so refusing one rules out
    # entity expansion before the parser sees the file. Any processing
    # instruction but the XML declaration is refused, xml-stylesheet included.
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.IGNORECASE):
        return "a DOCTYPE or entity declaration"
    if re.search(r"<\?(?!xml\s)", text, re.IGNORECASE):
        return "a processing instruction"
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as err:
        return f"XML that can't be read ({err})"

    if root.tag != f"{_SVG_NS}svg":
        return f"a root element <{_local(root.tag)}> that isn't an SVG <svg>"
    for element in root.iter():
        tag = element.tag
        if not isinstance(tag, str) or not tag.startswith(_SVG_NS):
            return f"an element outside the SVG namespace ({tag})"
        name = tag[len(_SVG_NS):]
        if name not in LOGO_ELEMENTS:
            return f"a <{name}> element"
        if name == "style" and element.text:
            problem = _css_problem(element.text)
            if problem:
                return f"a <style> with {problem}"
        for attribute, value in element.attrib.items():
            if attribute == _XLINK_HREF:
                attribute = "href"
            elif attribute == _XML_SPACE:
                continue
            elif attribute.startswith("{"):
                return f"an attribute outside the SVG namespace ({attribute}) on <{name}>"
            if attribute.lower().startswith("on"):
                return f"an event handler ({attribute}) on <{name}>"
            if attribute not in LOGO_ATTRIBUTES and not attribute.startswith("data-"):
                return f"a {attribute} attribute on <{name}>"
            if attribute == "href" and not value.strip().startswith("#"):
                return f"an href to {value.strip()[:60]!r} on <{name}>"
            problem = _css_problem(value)
            if problem:
                return f"{problem} in {attribute} on <{name}>"
    return None


def _css_problem(css: str) -> str | None:
    """A url() to anything but an id in the same file, or CSS that can fetch or run something."""
    for match in _CSS_URL.finditer(css):
        if not match.group(2).strip().startswith("#"):
            return f"a url() to {match.group(2).strip()[:60]!r}"
    for pattern, what in _CSS_RISKY:
        if pattern.search(css):
            return what
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# --- Sanitising a rendered page ---


def sanitize_html(rendered: str) -> tuple[str, list[str]]:
    """Sanitise a connector page's rendered HTML: (the HTML to publish, what sanitising removed).

    nh3 parses the HTML as a browser does and re-serialises only what the
    allowlists keep, so the published page can't run script whatever the README
    held. What was removed is found by comparing the tags and attributes of the
    two versions; that comparison only words the error, since the sanitised HTML
    is what gets published.
    """
    try:
        import nh3
    except ImportError as err:
        raise CatalogError(
            "nh3 is needed to publish connector pages and isn't installed: "
            "python3 -I -m pip install --require-hashes -r .github/scripts/docs/requirements.txt"
        ) from err
    prepared = placeholders_as_text(rendered)
    cleaned = nh3.clean(
        prepared,
        tags=SAFE_TAGS,
        attributes=SAFE_ATTRIBUTES,
        attribute_filter=_drop_reserved_ids,
        url_schemes=SAFE_URL_SCHEMES,
        filter_style_properties=SAFE_STYLE_PROPERTIES,
        strip_comments=True,
        link_rel=None,
    )
    removed = _markup(prepared) - _markup(cleaned)
    return cleaned, sorted(removed)


def placeholders_as_text(rendered: str) -> str:
    """Escape each tag that names no real element and has no attribute values, such as <WEBHOOK_URL>."""

    def as_text(match: re.Match) -> str:
        if match.group(1).lower() in KNOWN_ELEMENTS:
            return match.group(0)
        return html.escape(match.group(0), quote=False)

    return _BARE_TAG.sub(as_text, rendered)


def _drop_reserved_ids(tag: str, attribute: str, value: str) -> str | None:
    """nh3 attribute_filter: drop an id or name in Material's reserved "__" namespace."""
    if attribute in ("id", "name") and _RESERVED_ID.match(value):
        return None
    return value


class _MarkupCounter(HTMLParser):
    """Counts each start tag, and each attribute with its value, in a fragment of HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: Counter = Counter()

    def handle_starttag(self, tag, attrs):
        self.items[f"<{tag}>"] += 1
        for attr, value in attrs:
            value = "" if value is None else value
            if attr == "style":
                # nh3 re-serialises a style it keeps, so compare declarations
                value = ";".join(sorted(d.replace(" ", "").lower() for d in value.split(";") if d.strip()))
            shown = value if len(value) <= 60 else value[:57] + "..."
            self.items[f"{attr}={shown!r} on <{tag}>"] += 1

    handle_startendtag = handle_starttag


def _markup(fragment: str) -> Counter:
    counter = _MarkupCounter()
    counter.feed(fragment)
    counter.close()
    return counter.items


def _scan_lines(readme: str):
    """Yield (line number, line, inside a fenced code block) for each line, fence lines counting as code."""
    fence = None
    for number, line in enumerate(readme.split("\n"), start=1):
        match = _FENCE.match(line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            yield number, line, True
        elif match:
            fence = match.group(1)
            yield number, line, True
        else:
            yield number, line, False


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
