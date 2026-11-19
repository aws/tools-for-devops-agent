"""
MkDocs hook: generates catalog data for skills and custom agents.

At build time:
- Scans skills/*/SKILL.md, extracts metadata, and writes
  docs/javascripts/skills-data.json.
- Scans custom-agents/*/README.md, extracts metadata, and writes
  docs/javascripts/agents-data.json.

The JS on the catalog pages reads these JSON files to render cards
and group-by buttons dynamically.

This also generates individual doc stubs for skills and custom agents
that don't have a docs page yet, so new entries appear on the site
automatically.

Skills whose metadata.tier is aws-support-managed are left out of all of
this while extra.skills_catalog.show_aws_support_managed in mkdocs.yml is
false, which keeps that tier off the site until it launches, and so are
skills whose frontmatter can't be read, since their tier is unknown. With
no catalog entry and no page, the site search doesn't find them either.
While it's false, a page that names one of them, by its folder name or its
display name, fails the strict build, so the name can't reach the site
through another page.
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path

import yaml

try:
    from mkdocs.exceptions import PluginError
except ImportError:  # the unit tests run without mkdocs installed
    class PluginError(Exception):
        pass

log = logging.getLogger("mkdocs.hooks.skills_catalog")

# Skills of this tier stay off the site until mkdocs.yml sets
# extra.skills_catalog.show_aws_support_managed to true.
AWS_SUPPORT_MANAGED = "aws-support-managed"
SHOW_AWS_SUPPORT_MANAGED = "show_aws_support_managed"

# The frontmatter, found as .github/scripts/skill_checks.py finds it.
_FRONTMATTER = re.compile(r"\A---\r?\n(?:(.*?)\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)

# The skills this build leaves off the site, each with why, for on_page_content.
# Set by on_pre_build.
_HIDDEN: dict = {}

# For each of those skills, the longer names of other skills, custom agents,
# connectors and MCP servers that contain its name, for on_page_content.
# Set by on_pre_build.
_LONGER_NAMES: dict = {}

# The folders whose names are the names of things the site lists.
_TOOL_DIRS = ("skills", "custom-agents", "connectors", "mcp")

# metadata.aws-devops-agent-skills.agent-types carries the API values, because it
# sets which agents load the skill. The catalog shows them in readable form; a
# value with no entry here is displayed as-is.
AGENT_TYPE_LABELS = {
    "GENERIC": "All agents",
    "CHAT": "Chat tasks",
    "INCIDENT_TRIAGE": "Incident triage",
    "INCIDENT_RCA": "Incident RCA",
    "INCIDENT_MITIGATION": "Incident mitigation",
    "INCIDENT_UI": "Incident UI",
    "PREVENTION": "Improvement",
    "RELEASE_READINESS_REVIEW": "Release readiness review",
    "RELEASE_TESTING": "Release testing",
}


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a SKILL.md file (minimal parser, no deps)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}

    end = text.find("---", 3)
    if end == -1:
        return {}

    fm_text = text[3:end]
    result = {"_body": text[end + 3:].strip()}

    # Parse top-level keys (name, description)
    current_key = None
    current_value = ""

    for line in fm_text.splitlines():
        # Top-level key: value
        m = re.match(r'^(\w[\w\-.]*):\s*(.*)', line)
        if m and not line.startswith("  "):
            if current_key:
                result[current_key] = current_value.strip()
            current_key = m.group(1)
            current_value = m.group(2)
        elif current_key and line.startswith("  "):
            # Continuation or nested
            current_value += " " + line.strip()

    if current_key:
        result[current_key] = current_value.strip()

    # Parse metadata block specifically
    metadata = {}
    in_metadata = False
    for line in fm_text.splitlines():
        if line.strip() == "metadata:":
            in_metadata = True
            continue
        if in_metadata:
            if line and not line.startswith(" "):
                break
            m = re.match(r'^\s+([\w\-.]+ *):\s*"?([^"]*)"?\s*$', line)
            if m:
                metadata[m.group(1).strip()] = m.group(2).strip()

    result["metadata"] = metadata
    return result


def _show_aws_support_managed(config) -> bool:
    """extra.skills_catalog.show_aws_support_managed in mkdocs.yml, which must be true or false."""
    settings = (config.get("extra") or {}).get("skills_catalog")
    value = settings.get(SHOW_AWS_SUPPORT_MANAGED) if isinstance(settings, Mapping) else None
    if not isinstance(value, bool):
        raise PluginError(
            f"Skills catalog: set extra.skills_catalog.{SHOW_AWS_SUPPORT_MANAGED} in mkdocs.yml "
            "to true or false"
        )
    return value


def _hidden_skills(config_dir: str) -> dict:
    """The skills to leave off the site while the setting is false, each with why."""
    skills_dir = Path(config_dir) / "skills"
    if not skills_dir.is_dir():
        return {}
    return {
        skill_md.parent.name: why
        for skill_md in skills_dir.glob("*/SKILL.md")
        if skill_md.is_file() and (why := _why_hidden(skill_md.read_text(encoding="utf-8")))
    }


def _why_hidden(text: str) -> str | None:
    """Why a SKILL.md stays off the site while the setting is false, or None if it's listed.

    The tier is read as YAML: _parse_frontmatter keeps quotes and comments in a
    value, so it would miss tier: 'aws-support-managed', or the value followed by
    a comment. Frontmatter that is missing or can't be read as YAML hides the
    skill too, since its tier is unknown. The publishing check fails such a
    skill anyway.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return "its tier can't be read: SKILL.md has no frontmatter between --- lines"
    try:
        root = yaml.compose(match.group(1) or "", Loader=yaml.SafeLoader)
    except yaml.YAMLError as err:
        mark, problem = getattr(err, "problem_mark", None), getattr(err, "problem", None)
        if mark and problem:
            # The mark counts lines from the frontmatter, which starts on line 2 of SKILL.md.
            return f"its tier can't be read: line {mark.line + 2} of SKILL.md isn't valid YAML ({problem})"
        return "its tier can't be read: its frontmatter isn't valid YAML"
    except RecursionError:
        return "its tier can't be read: its frontmatter is nested too deeply"
    if any(
        isinstance(tier, yaml.ScalarNode) and tier.value == AWS_SUPPORT_MANAGED
        for metadata in _values(root, "metadata")
        for tier in _values(metadata, "tier")
    ):
        return f"it's {AWS_SUPPORT_MANAGED}"
    return None


def _values(node, key: str) -> list:
    """The value nodes of key in a YAML mapping node.

    A repeated key, which the publishing check refuses, gives several.
    """
    if not isinstance(node, yaml.MappingNode):
        return []
    return [value for k, value in node.value if isinstance(k, yaml.ScalarNode) and k.value == key]


def _build_catalog(config_dir: str) -> list:
    """Scan all skills and build catalog entries."""
    skills_dir = Path(config_dir) / "skills"
    catalog = []

    if not skills_dir.is_dir():
        return catalog

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir():
            continue

        skill_md = skill_path / "SKILL.md"
        readme = skill_path / "README.md"

        if not skill_md.is_file():
            continue

        fm = _parse_frontmatter(skill_md)
        metadata = fm.get("metadata", {})
        name = fm.get("name", skill_path.name)

        # Extract description from README first line after title, or from frontmatter
        description = ""
        if readme.is_file():
            readme_text = readme.read_text(encoding="utf-8")
            # Find first paragraph after the title
            lines = readme_text.split("\n")
            past_title = False
            for line in lines:
                if line.startswith("# "):
                    past_title = True
                    continue
                if past_title and line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break

        if not description:
            description = fm.get("description", "")[:200]

        # Convert markdown links to HTML (rendered inside innerHTML in cards)
        description = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" target="_blank" rel="noopener">\1</a>',
            description
        )
        # Convert markdown bold to HTML
        description = re.sub(
            r'\*\*([^*]+)\*\*',
            r'<strong>\1</strong>',
            description
        )

        # Collect all aws-devops-agent-skills.* dimensions
        dimensions = {}
        for key, value in metadata.items():
            if key.startswith("aws-devops-agent-skills."):
                dim_name = key.replace("aws-devops-agent-skills.", "")
                values = [v.strip() for v in value.split(",") if v.strip()]
                if dim_name == "agent-types":
                    values = [AGENT_TYPE_LABELS.get(v, v) for v in values]
                dimensions[dim_name] = values

        catalog.append({
            "id": skill_path.name,
            "name": _format_name(skill_path.name),
            "description": description,
            "dimensions": dimensions,
            "author": metadata.get("author", ""),
            "version": metadata.get("version", ""),
        })

    return catalog


def _format_name(skill_id: str) -> str:
    """Convert skill-id to display name: aws-health-events -> AWS Health Events."""
    words = skill_id.split("-")
    # Capitalize known acronyms
    acronyms = {"aws", "eks", "rds", "rca", "mcp", "crm", "eos", "iac"}
    return " ".join(
        w.upper() if w.lower() in acronyms else w.capitalize()
        for w in words
    )


def _name_pattern(name: str) -> re.Pattern:
    """A name as a page writes it: its folder name, or its display name.

    For aws-health-events, the folder name counts in any case (aws-health-events,
    AWS-Health-Events), and the display name with each word starting with a
    capital letter (AWS Health Events, Aws Health Events, AWS HEALTH EVENTS), with
    a line break, a blockquote's > or &nbsp; wherever a space can go. Lowercase
    words don't count, since "triage AWS Health events" is about the events, not
    the skill. A name counts only as a whole word: no letter, digit or hyphen
    touches it, so my-aws-health-events and aws-health-events-report don't name
    it. Underscores, asterisks and backticks can, since Markdown uses them for
    emphasis and code.
    """
    words = name.split("-")
    folder = "-".join(re.escape(word) for word in words)
    display = r"(?:[\s>]|&nbsp;)+".join(
        re.escape(word[0].upper()) + (f"(?i:{re.escape(word[1:])})" if word[1:] else "") for word in words
    )
    return re.compile(rf"(?<![A-Za-z0-9-])(?:(?i:{folder})|{display})(?![A-Za-z0-9-])")


def _tool_names(config_dir: str) -> set:
    """The names of the skills, custom agents, connectors and MCP servers: their folder names."""
    root = Path(config_dir)
    return {
        path.name
        for folder in _TOOL_DIRS
        if (root / folder).is_dir()
        for path in (root / folder).iterdir()
        if path.is_dir()
    }


def _longer_names(name: str, names) -> list:
    """The names in names that contain name as whole words, such as aws-health-events-report for aws-health-events."""
    return sorted(other for other in names if other != name and f"-{name}-" in f"-{other}-")


def on_pre_build(config, **kwargs):
    """Generate skills-data.json and skill doc stubs before the build."""
    config_dir = config["docs_dir"].replace("/docs", "")
    hidden = {} if _show_aws_support_managed(config) else _hidden_skills(config_dir)
    _HIDDEN.clear()
    _HIDDEN.update(hidden)
    names = _tool_names(config_dir) if hidden else set()
    _LONGER_NAMES.clear()
    _LONGER_NAMES.update({skill_id: _longer_names(skill_id, names) for skill_id in hidden})
    catalog = [skill for skill in _build_catalog(config_dir) if skill["id"] not in hidden]

    # Write JSON for the JS to consume (only if changed, to avoid dev-server loop)
    js_dir = Path(config["docs_dir"]) / "javascripts"
    js_dir.mkdir(parents=True, exist_ok=True)
    data_path = js_dir / "skills-data.json"
    new_content = json.dumps(catalog, indent=2)
    if data_path.is_file() and data_path.read_text(encoding="utf-8") == new_content:
        pass  # No change, skip write to avoid triggering file watcher
    else:
        data_path.write_text(new_content, encoding="utf-8")

    # Generate stub pages for skills that don't have a docs page yet
    skills_docs_dir = Path(config["docs_dir"]) / "skills"
    skills_docs_dir.mkdir(parents=True, exist_ok=True)

    for skill in catalog:
        doc_path = skills_docs_dir / f"{skill['id']}.md"
        _generate_skill_stub(doc_path, skill, config_dir)

    # An earlier build may have written a page for a hidden skill. It would still
    # be published, and found by the site search, so remove it.
    for skill_id, why in sorted(hidden.items()):
        (skills_docs_dir / f"{skill_id}.md").unlink(missing_ok=True)
        log.info(
            "Skills catalog: leaving %s off the site while extra.skills_catalog.%s is false, since %s",
            skill_id,
            SHOW_AWS_SUPPORT_MANAGED,
            why,
        )

    # Inject skill pages into nav in memory
    _update_nav(config, catalog)


def on_page_content(html_text, page, **kwargs):
    """Fail the strict build when a page names a skill this build leaves off the site.

    The check reads page.markdown here rather than in on_page_markdown, because by
    now every hook's on_page_markdown has run, including blogs_catalog.py's, which
    adds the Blogs page's posts. It reads the page's front matter too, which can
    set its title. Every catalog entry that names a skill comes from a page that
    names it too, so this covers the cards as well.

    A page names a skill with its folder name or its display name (see
    _name_pattern). The longer name of another skill, custom agent, connector or
    MCP server doesn't name it, even as a display name: if a custom agent is
    called aws-health-events-report, AWS Health Events Report names the agent,
    not the aws-health-events skill.
    """
    if not _HIDDEN:
        return html_text
    source = page.markdown + "\n" + _text(getattr(page, "meta", None) or {})
    for skill_id, why in sorted(_HIDDEN.items()):
        text = source
        for longer in _LONGER_NAMES.get(skill_id, ()):
            text = _name_pattern(longer).sub("\0", text)
        match = _name_pattern(skill_id).search(text)
        if match:
            shown = " ".join(re.sub(r"&nbsp;|>", " ", match.group()).split())
            log.warning(
                "Skills catalog: %s names %s, which is left off the site while extra.skills_catalog.%s "
                "is false, since %s",
                page.file.src_uri,
                skill_id if shown == skill_id else f'{skill_id} as "{shown}"',
                SHOW_AWS_SUPPORT_MANAGED,
                why,
            )
    return html_text


def _text(value) -> str:
    """The text in a page's front matter: every key and value, one per line."""
    if isinstance(value, Mapping):
        return "\n".join(_text(item) for pair in value.items() for item in pair)
    if isinstance(value, (list, tuple)):
        return "\n".join(_text(item) for item in value)
    return str(value)


def _generate_skill_stub(doc_path: Path, skill: dict, config_dir: str):
    """Generate a minimal skill doc page from its README (only if changed)."""
    repo_url = "https://github.com/aws/tools-for-devops-agent"
    github_link = (
        f'<a href="{repo_url}/tree/main/skills/{skill["id"]}" '
        f'target="_blank" rel="noopener" class="md-button">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" style="vertical-align: text-bottom; margin-right: 0.3rem;"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
        f'View on GitHub</a>\n\n'
    )

    # Build metadata block (author + dimension tags)
    meta_block = _build_skill_meta_block(skill)

    readme = Path(config_dir) / "skills" / skill["id"] / "README.md"
    if readme.is_file():
        readme_content = readme.read_text(encoding="utf-8")
        # Insert the GitHub link and metadata after the first heading
        lines = readme_content.split("\n", 1)
        if len(lines) == 2 and lines[0].startswith("# "):
            content = lines[0] + "\n\n" + github_link + meta_block + lines[1]
        else:
            content = github_link + meta_block + readme_content
    else:
        content = f"# {skill['name']}\n\n{github_link}{meta_block}{skill['description']}\n"

    if doc_path.is_file() and doc_path.read_text(encoding="utf-8") == content:
        return  # No change, skip write
    doc_path.write_text(content, encoding="utf-8")


def _author_link(author: str) -> str:
    """A user links to their profile; a team (org/team) to its organization, since team pages need sign-in."""
    profile = author.split("/", 1)[0]
    return (
        f'<a href="https://github.com/{html.escape(profile)}" target="_blank" rel="noopener">'
        f'<strong>{html.escape(author)}</strong></a>'
    )


def _build_skill_meta_block(skill: dict) -> str:
    """Build an HTML block showing author and dimension tags for a skill page."""
    parts = []

    # Author line, one GitHub link per comma-separated author
    authors = [a.strip() for a in skill.get("author", "").split(",") if a.strip()]
    if authors:
        links = ", ".join(_author_link(a) for a in authors)
        parts.append(f'<div class="skill-meta"><span class="skill-author">by {links}</span></div>')

    # Dimension tags
    dimensions = skill.get("dimensions", {})
    tags_html = []
    tag_class_map = {
        "agent-types": "tag-agent",
        "aws-services": "tag-service",
        "technical-domains": "tag-domain",
    }
    for dim_key, values in dimensions.items():
        css_class = tag_class_map.get(dim_key, "tag-domain")
        for value in values:
            tags_html.append(f'<span class="tag {css_class}">{value}</span>')

    if tags_html:
        parts.append(
            '<div class="skill-tags">' + " ".join(tags_html) + '</div>'
        )

    if parts:
        return '<div class="skill-page-meta">\n' + "\n".join(parts) + "\n</div>\n\n"
    return ""


def _update_nav(config, catalog):
    """Inject skill pages into the nav in memory (no file writes).
    
    Looks for Skills > Catalog section and appends skill pages there.
    """
    nav = config.get("nav")
    if not nav:
        return

    # Find the Skills section
    for item in nav:
        if isinstance(item, dict) and "Skills" in item:
            skills_nav = item["Skills"]

            # Find the Catalog subsection
            for entry in skills_nav:
                if isinstance(entry, dict) and "Catalog" in entry:
                    catalog_nav = entry["Catalog"]

                    # Collect existing paths
                    existing_paths = set()
                    for sub in catalog_nav:
                        if isinstance(sub, dict):
                            for path in sub.values():
                                existing_paths.add(path)
                        elif isinstance(sub, str):
                            existing_paths.add(sub)

                    # Add skill pages
                    for skill in catalog:
                        page_path = f"skills/{skill['id']}.md"
                        if page_path not in existing_paths:
                            catalog_nav.append({skill["name"]: page_path})
                    break
            break
