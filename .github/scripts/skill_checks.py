"""Publishing rules for one skill folder, skills/<name>/.

Every function here works on an in-memory copy of a skill folder, so the same
rules run on Git objects in CI (validate_skills.py), on the cases in
skill-rules/conformance-cases.json, and in the unit tests under tests/.

The rules exist because skills on `main` are published as one set: the
catalog publisher validates every skill before it writes anything, and one
skill that breaks a rule stops every skill from publishing.
See the "Skill Publishing Rules" section of CONTRIBUTING.md.
"""

from __future__ import annotations

import base64
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

RULES_DIR_DISPLAY = ".github/scripts/skill-rules"
AGENT_TYPES_FILE = "agent-types.json"
VOCABULARY_FILE = "vocabulary.json"
PUBLISHED_FILES_FILE = "published-files.json"

NAME_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_TITLE_LENGTH = 100
MAX_SUMMARY_LENGTH = 200

VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
# Only ever accepted for the merge-base copy of a skill, so that a skill still
# on a two-part version can be compared while it is being fixed. The fix
# changes SKILL.md, so it needs a version above the old one: 2.6 -> 2.6.1.
TWO_PART_VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")

# Patterns are applied with fullmatch: a `$` would also match before a trailing
# newline, which a YAML block scalar (`version: |`) produces.
#
# GitHub's own rule for usernames: alphanumerics and single hyphens, no leading
# or trailing hyphen, at most 39 characters.
GITHUB_LOGIN_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")

DIMENSION_PREFIX = "aws-devops-agent-skills."
DIMENSIONS = ("agent-types", "aws-services", "technical-domains")

# The Agent Skills specification's frontmatter fields, plus the optional
# display `title`. Anything else is reported as a warning.
TOP_LEVEL_KEYS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools", "title")

# Package limits. A published skill is capped at a 1 MiB zip and 100 files. Zip sizes vary a little by tool, so the check leaves a
# 64 KiB margin, and warns once a skill passes 90% of what is left.
MAX_PUBLISHED_FILES = 100
ZIP_LIMIT_BYTES = 1_048_576 - 65_536
ZIP_WARNING_RATIO = 0.9
MAX_PATH_LENGTH = 512
SEGMENT_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)
REGULAR_FILE_MODE = "100644"
TEXT_EXTENSIONS = frozenset({"md", "txt", "json", "yaml", "yml", "xml", "csv", "tsv", "html", "htm", "svg"})
GITIGNORE_EXTENSION_PATTERN = re.compile(r"^!\*\.([A-Za-z0-9]+)\s*$")

# Content that must never be public. Matched on bytes in every file of the
# skill folder, evals included, since the whole repository is public.
AWS_ACCESS_KEY_PATTERN = re.compile(rb"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")
DOCUMENTED_EXAMPLE_KEYS = frozenset({b"AKIA" + b"IOSFODNN7EXAMPLE"})
PRIVATE_KEY_PATTERN = re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")

# Characters that render as nothing, or reorder the text around them, so a
# reviewer reading the diff can't see what the model will read: zero-width
# characters, bidirectional controls, the byte order mark, and Unicode tags.
INVISIBLE_PATTERN = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")

# Markdown that skill previews won't render the way the source reads. Warnings
# only: placeholders such as <object> and HTML comments are common and harmless.
ACTIVE_HTML_PATTERN = re.compile(
    r"<(script|iframe|embed|form|style|link|meta)\b[^>]*>|<(object|img)\s[^>]*>", re.IGNORECASE
)
JAVASCRIPT_URL_PATTERN = re.compile(r"javascript:", re.IGNORECASE)
HTTP_LINK_PATTERN = re.compile(r"\]\(\s*http://", re.IGNORECASE)

FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)

STR_TAG = "tag:yaml.org,2002:str"
_SCALAR_KINDS = {
    "tag:yaml.org,2002:int": "a number",
    "tag:yaml.org,2002:float": "a number",
    "tag:yaml.org,2002:bool": "true or false",
    "tag:yaml.org,2002:null": "empty",
    "tag:yaml.org,2002:timestamp": "a date",
}

# YAML features that different parsers read differently, or that let one part
# of the frontmatter silently change another. Other tools parse the same text,
# in other languages, so the frontmatter is limited to plain block mappings and
# scalars that every parser reads the same way.
_FORBIDDEN_TOKENS = (
    (yaml.AnchorToken, "anchors (&)"),
    (yaml.AliasToken, "aliases (*)"),
    (yaml.TagToken, "tags (! or !!)"),
    (yaml.DirectiveToken, "directives (%)"),
    (yaml.DocumentStartToken, "document markers (--- or ...)"),
    (yaml.DocumentEndToken, "document markers (--- or ...)"),
    (yaml.FlowMappingStartToken, "flow collections ({...} or [...])"),
    (yaml.FlowSequenceStartToken, "flow collections ({...} or [...])"),
)


@dataclass(frozen=True)
class Entry:
    """One file in a skill folder. `path` is relative to the folder; `mode` is the Git file mode."""

    path: str
    mode: str
    data: bytes


@dataclass
class SkillTree:
    name: str
    entries: dict[str, Entry] = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    """A rule result. `severity` is "error" (blocks the pull request) or "warning"."""

    severity: str
    message: str
    path: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class Rules:
    """The data the rules read from skill-rules/."""

    agent_types: frozenset[str]
    vocabulary: dict[str, frozenset[str]]
    aliases: dict[str, str]
    allowed_extensions: frozenset[str]
    published_excludes: tuple[str, ...]
    # Display agent type -> AgentType values, or None while no mapping is agreed.
    display_agent_types: dict[str, tuple[str, ...] | None] = field(default_factory=dict)


@dataclass
class SkillInfo:
    """What later rules need from a parsed SKILL.md."""

    name: str
    version: tuple[int, int, int] | None
    metadata: dict[str, str]


def load_rules(rules_dir: Path, gitignore_text: str) -> Rules:
    """Read the rule data files and the extension allowlist in skills/.gitignore.

    Raises ValueError when any of them is malformed, so the check fails closed.
    """
    agent_types = _read_json(rules_dir / AGENT_TYPES_FILE)
    vocabulary = _read_json(rules_dir / VOCABULARY_FILE)
    published = _read_json(rules_dir / PUBLISHED_FILES_FILE)
    try:
        excludes = _string_list(published["exclude"], f"{PUBLISHED_FILES_FILE} exclude")
        if not excludes or not all("/" not in e.rstrip("/") for e in excludes):
            raise TypeError(f"{PUBLISHED_FILES_FILE}: exclude must list root-level names, folders ending in /")
        values = _string_list(agent_types["values"], f"{AGENT_TYPES_FILE} values")
        dimensions = vocabulary["values"]
        aliases = vocabulary["aliases"]
        if not isinstance(dimensions, dict) or set(dimensions) != set(DIMENSIONS):
            raise TypeError(f"{VOCABULARY_FILE}: values must have exactly the keys {', '.join(DIMENSIONS)}")
        if not isinstance(aliases, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and k and v for k, v in aliases.items()
        ):
            raise TypeError(f"{VOCABULARY_FILE}: aliases must map non-empty strings to non-empty strings")
        vocabulary_sets = {dim: frozenset(_string_list(dimensions[dim], f"{VOCABULARY_FILE} {dim}")) for dim in DIMENSIONS}
        mapping = _display_mapping(agent_types.get("display_mapping"), frozenset(values), vocabulary_sets["agent-types"])
        return Rules(
            agent_types=frozenset(values),
            vocabulary=vocabulary_sets,
            aliases=dict(aliases),
            allowed_extensions=allowed_extensions_from_gitignore(gitignore_text),
            published_excludes=tuple(excludes),
            display_agent_types=mapping,
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"malformed rule data in {rules_dir}: {exc}") from exc


def _display_mapping(raw, agent_types: frozenset[str], display_values: frozenset[str]) -> dict:
    """agent-types.json display_mapping, checked against the AgentType values and the display vocabulary."""
    if not isinstance(raw, dict) or set(raw) != set(display_values):
        raise TypeError(
            f"{AGENT_TYPES_FILE}: display_mapping must have one entry for each agent-types value in {VOCABULARY_FILE}"
        )
    mapping = {}
    for display, targets in raw.items():
        if targets is not None:
            targets = _string_list(targets, f"{AGENT_TYPES_FILE} display_mapping[{display!r}]")
            unknown = [target for target in targets if target not in agent_types]
            if unknown:
                raise TypeError(f"{AGENT_TYPES_FILE}: display_mapping[{display!r}] has unknown values {unknown}")
            targets = tuple(targets)
        mapping[display] = targets
    return mapping


def runtime_agent_types(metadata: dict[str, str], rules: Rules) -> tuple[list[str], bool]:
    """The AgentType values a skill installs for, and whether they are only the GENERIC fallback.

    metadata.agent_types wins when set. Otherwise the display values in
    aws-devops-agent-skills.agent-types are mapped through display_mapping.
    With neither, the skill installs as GENERIC, for all agents.
    """
    explicit = metadata.get("agent_types")
    if explicit is not None:
        return [part for part in _split(explicit) if part], False
    derived: list[str] = []
    for display in _split(metadata.get(DIMENSION_PREFIX + "agent-types", "")):
        for agent in rules.display_agent_types.get(display) or ():
            if agent not in derived:
                derived.append(agent)
    return (derived, False) if derived else (["GENERIC"], True)


def _string_list(value, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise TypeError(f"{label} must be a list of non-empty strings")
    return value


def allowed_extensions_from_gitignore(text: str) -> frozenset[str]:
    """The extensions skills/.gitignore allows, from its `!*.<ext>` lines, lowercased."""
    extensions = frozenset(
        match[1].lower() for line in text.splitlines() if (match := GITIGNORE_EXTENSION_PATTERN.match(line.strip()))
    )
    if not extensions:
        raise ValueError("skills/.gitignore lists no allowed extensions (lines such as !*.md)")
    return extensions


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def parse_version(text: str, *, allow_two_part: bool = False) -> tuple[int, int, int] | None:
    """`MAJOR.MINOR.PATCH` as a tuple, or None. `allow_two_part` reads `2.6` as 2.6.0."""
    match = VERSION_PATTERN.fullmatch(text)
    if match:
        return (int(match[1]), int(match[2]), int(match[3]))
    match = TWO_PART_VERSION_PATTERN.fullmatch(text) if allow_two_part else None
    if match:
        return (int(match[1]), int(match[2]), 0)
    return None


def check_skill(tree: SkillTree, rules: Rules) -> tuple[list[Finding], SkillInfo | None]:
    """Every rule that needs only this copy of the skill. Returns the findings and, when SKILL.md parses, its info."""
    findings: list[Finding] = []
    skill_md = tree.entries.get("SKILL.md")
    info = None
    if skill_md is None:
        findings.append(Finding("error", "the skill folder has no SKILL.md"))
    else:
        info = _check_skill_md(tree.name, skill_md.data, rules, findings)
    _check_package(tree, rules, findings)
    _check_content(tree, rules, findings)
    return findings, info


def published_files(tree: SkillTree, rules: Rules) -> dict[str, Entry]:
    """The entries that are published and that customers install: the folder minus the excluded names."""
    folders = tuple(e for e in rules.published_excludes if e.endswith("/"))
    names = frozenset(e for e in rules.published_excludes if not e.endswith("/"))
    return {
        path: entry
        for path, entry in tree.entries.items()
        if path not in names and not path.startswith(folders)
    }


def build_zip(files: dict[str, bytes]) -> bytes:
    """A reproducible zip: entries sorted by UTF-8 path, deflate level 6, all dated 1980-01-01."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(files, key=lambda p: p.encode("utf-8", "surrogateescape")):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[path], compresslevel=6)
    return buffer.getvalue()


# --- SKILL.md -----------------------------------------------------------------


class _Report:
    """Collects findings for SKILL.md. Frontmatter starts on line 2, so YAML line N is file line N + 2."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings

    def error(self, message: str, line: int | None = None) -> None:
        self.findings.append(Finding("error", message, "SKILL.md", line))

    def warning(self, message: str, line: int | None = None) -> None:
        self.findings.append(Finding("warning", message, "SKILL.md", line))


def _line(node: Node) -> int:
    return node.start_mark.line + 2


def _kind(node: Node) -> str:
    if isinstance(node, MappingNode):
        return "a mapping"
    if isinstance(node, SequenceNode):
        return "a list"
    return _SCALAR_KINDS.get(node.tag, "not text")


def _check_skill_md(folder: str, data: bytes, rules: Rules, findings: list[Finding]) -> SkillInfo | None:
    report = _Report(findings)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error("SKILL.md is not valid UTF-8", line=data.count(b"\n", 0, exc.start) + 1)
        return None

    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        report.error(
            "SKILL.md must start with a --- line, then the YAML frontmatter, then a closing --- line", line=1
        )
        return None
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        report.error("the frontmatter has no closing --- line", line=1)
        return None
    frontmatter = match.group(1)

    root = _parse_frontmatter(frontmatter, report)
    if root is None:
        return None
    if not isinstance(root, MappingNode):
        report.error("the frontmatter must be a mapping of keys to values, such as name: my-skill", line=2)
        return None

    top = _mapping_items(root, "", report)
    for key, (key_node, _) in top.items():
        if key not in TOP_LEVEL_KEYS:
            report.warning(
                f'unknown top-level key "{key}"; the Agent Skills specification defines '
                "name, description, license, compatibility, metadata and allowed-tools",
                line=_line(key_node),
            )

    name = _check_name(folder, top, report)
    _check_description(top, report)
    _check_title(top, report)
    for key in ("license", "compatibility", "allowed-tools"):
        if key in top:
            _text(top, key, key, report)

    metadata, version = _check_metadata(top, rules, report)
    return SkillInfo(name=name or folder, version=version, metadata=metadata)


def _parse_frontmatter(frontmatter: str, report: _Report) -> Node | None:
    """The composed YAML node tree, or None after reporting why the frontmatter can't be read safely."""
    try:
        forbidden = [
            (token, what)
            for token in yaml.scan(frontmatter, Loader=yaml.SafeLoader)
            for kind, what in _FORBIDDEN_TOKENS
            if isinstance(token, kind)
        ]
    except yaml.YAMLError as exc:
        _report_yaml_error(exc, report)
        return None
    for token, what in forbidden:
        report.error(f"the frontmatter uses {what}, which is not allowed", line=token.start_mark.line + 2)
    if forbidden:
        return None
    try:
        root = yaml.compose(frontmatter, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        _report_yaml_error(exc, report)
        return None
    except RecursionError:
        report.error("the frontmatter is nested too deeply to read", line=2)
        return None
    if root is None:
        report.error("the frontmatter is empty", line=2)
    return root


def _report_yaml_error(exc: yaml.YAMLError, report: _Report) -> None:
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or str(exc)
    report.error(f"the frontmatter is not valid YAML: {problem}", line=mark.line + 2 if mark else None)


def _mapping_items(node: MappingNode, prefix: str, report: _Report) -> dict[str, tuple[ScalarNode, Node]]:
    items: dict[str, tuple[ScalarNode, Node]] = {}
    for key_node, value_node in node.value:
        if not (isinstance(key_node, ScalarNode) and key_node.tag == STR_TAG):
            report.error("frontmatter keys must be plain text", line=_line(key_node))
            continue
        if key_node.value in items:
            report.error(f'duplicate key "{prefix}{key_node.value}"', line=_line(key_node))
            continue
        items[key_node.value] = (key_node, value_node)
    return items


def _text(items: dict, key: str, label: str, report: _Report) -> str | None:
    """The string value of `key`, or None after reporting that it isn't text. A missing key returns None silently."""
    if key not in items:
        return None
    key_node, value_node = items[key]
    if isinstance(value_node, ScalarNode) and value_node.tag == STR_TAG:
        return value_node.value
    message = f'"{label}" must be text, not {_kind(value_node)}'
    if isinstance(value_node, ScalarNode):
        message += f'. Put the value in quotes, for example {key}: "{value_node.value}"'
    report.error(message, line=_line(key_node))
    return None


def _single_line(value: str) -> bool:
    return "\n" not in value.strip("\n")


def _check_name(folder: str, top: dict, report: _Report) -> str | None:
    if "name" not in top:
        report.error('"name" is required')
        return None
    name = _text(top, "name", "name", report)
    if name is None:
        return None
    line = _line(top["name"][0])
    if len(name) > MAX_NAME_LENGTH:
        report.error(f'"name" is {len(name):,} characters; the limit is {MAX_NAME_LENGTH}', line=line)
    if not NAME_PATTERN.fullmatch(name):
        report.error('"name" must be lowercase letters, digits and single hyphens, such as my-skill', line=line)
    if name != folder:
        report.error(
            f'"name" is "{name}" but the folder is "{folder}"; they must match. '
            "A skill's folder path is its permanent identity",
            line=line,
        )
    return name


def _check_description(top: dict, report: _Report) -> None:
    if "description" not in top:
        report.error('"description" is required')
        return
    description = _text(top, "description", "description", report)
    if description is None:
        return
    line = _line(top["description"][0])
    if not description.strip():
        report.error('"description" must not be empty', line=line)
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        report.error(
            f'"description" is {len(description):,} characters; the limit is {MAX_DESCRIPTION_LENGTH:,}', line=line
        )


def _check_title(top: dict, report: _Report) -> None:
    title = _text(top, "title", "title", report)
    if title is None:
        return
    line = _line(top["title"][0])
    if not _single_line(title):
        report.error('"title" must be a single line', line=line)
    if len(title.strip()) > MAX_TITLE_LENGTH:
        report.error(f'"title" is {len(title.strip()):,} characters; the limit is {MAX_TITLE_LENGTH}', line=line)


def _check_metadata(top: dict, rules: Rules, report: _Report) -> tuple[dict[str, str], tuple[int, int, int] | None]:
    if "metadata" not in top:
        report.error('"metadata" is required, with at least author and version')
        return {}, None
    key_node, node = top["metadata"]
    metadata_line = _line(key_node)
    if not isinstance(node, MappingNode):
        report.error('"metadata" must be a mapping, with one key: value pair per line', line=metadata_line)
        return {}, None

    items = _mapping_items(node, "metadata.", report)
    metadata: dict[str, str] = {}
    lines: dict[str, int] = {}
    for key in items:
        value = _text(items, key, f"metadata.{key}", report)
        if value is not None:
            metadata[key] = value
            lines[key] = _line(items[key][0])

    _check_author(metadata, items, lines, metadata_line, report)
    version = _check_version(metadata, items, lines, metadata_line, report)
    _check_summary(metadata, lines, metadata_line, report)
    _check_deprecated(metadata, lines, report)
    _check_agent_types(metadata, lines, rules, report)
    _check_dimensions(metadata, items, rules, report)
    return metadata, version


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",")]


def _check_author(metadata: dict, items: dict, lines: dict, metadata_line: int, report: _Report) -> None:
    if "author" not in items:
        report.error('"metadata.author" is required', line=metadata_line)
        return
    if "author" not in metadata:
        return
    if not all(GITHUB_LOGIN_PATTERN.fullmatch(part) for part in _split(metadata["author"])):
        report.error(
            '"metadata.author" must be one or more GitHub usernames separated by commas, '
            'for example "octocat" or "octocat, hubot"',
            line=lines["author"],
        )


def _check_version(
    metadata: dict, items: dict, lines: dict, metadata_line: int, report: _Report
) -> tuple[int, int, int] | None:
    if "version" not in items:
        report.error('"metadata.version" is required, for example version: "1.0.0"', line=metadata_line)
        return None
    if "version" not in metadata:
        return None
    version = parse_version(metadata["version"])
    if version is None:
        report.error(
            f'"metadata.version" is "{metadata["version"]}"; it must be MAJOR.MINOR.PATCH, for example "1.2.0", '
            "with no prefix or suffix",
            line=lines["version"],
        )
    return version


def _check_summary(metadata: dict, lines: dict, metadata_line: int, report: _Report) -> None:
    summary = metadata.get("summary")
    if summary is None:
        # Becomes an error once every existing skill has a summary.
        report.warning(
            '"metadata.summary" is missing. It will be required once every skill has one: '
            "one line of at most 200 characters, shown as the skill's card text in catalogs",
            line=metadata_line,
        )
        return
    if not _single_line(summary):
        report.error('"metadata.summary" must be a single line', line=lines["summary"])
    if len(summary.strip()) > MAX_SUMMARY_LENGTH:
        report.error(
            f'"metadata.summary" is {len(summary.strip()):,} characters; the limit is {MAX_SUMMARY_LENGTH}',
            line=lines["summary"],
        )


def _check_deprecated(metadata: dict, lines: dict, report: _Report) -> None:
    deprecated = metadata.get("deprecated")
    if deprecated is not None and deprecated not in ("true", "false"):
        report.error(
            '"metadata.deprecated" must be "true" or "false", in quotes, because metadata values are text',
            line=lines["deprecated"],
        )


def _check_agent_types(metadata: dict, lines: dict, rules: Rules, report: _Report) -> None:
    value = metadata.get("agent_types")
    if value is None:
        _, fallback = runtime_agent_types(metadata, rules)
        if fallback:
            display_key = DIMENSION_PREFIX + "agent-types"
            unmapped = [part for part in _split(metadata.get(display_key, "")) if part]
            reason = (
                "none of " + ", ".join(f'"{part}"' for part in unmapped) + " has an agent-type mapping yet"
                if unmapped
                else "it sets no agent types"
            )
            report.warning(
                f"{reason}, so the skill would load for all agents (GENERIC). Set {display_key} to a mapped "
                f"value or set metadata.agent_types; the mapping is in {RULES_DIR_DISPLAY}/{AGENT_TYPES_FILE}",
                line=lines.get(display_key),
            )
        return
    for part in _split(value):
        if not part:
            report.error('"metadata.agent_types" has an empty value between commas', line=lines["agent_types"])
        elif part not in rules.agent_types:
            report.error(
                f'"metadata.agent_types" has unknown value "{part}"; '
                f"allowed values are listed in {RULES_DIR_DISPLAY}/{AGENT_TYPES_FILE}",
                line=lines["agent_types"],
            )


def _check_dimensions(metadata: dict, items: dict, rules: Rules, report: _Report) -> None:
    for key in items:
        if not key.startswith(DIMENSION_PREFIX):
            continue
        dimension = key[len(DIMENSION_PREFIX):]
        line = _line(items[key][0])
        if dimension not in DIMENSIONS:
            report.error(
                f'"metadata.{key}" is not a known dimension; use one of: '
                + ", ".join(DIMENSION_PREFIX + d for d in DIMENSIONS),
                line=line,
            )
            continue
        if key not in metadata:
            continue
        approved = rules.vocabulary.get(dimension, frozenset())
        for part in _split(metadata[key]):
            if not part:
                report.error(f'"metadata.{key}" has an empty value between commas', line=line)
            elif part not in approved:
                hint = (
                    f'use "{rules.aliases[part]}"'
                    if part in rules.aliases
                    else f"approved values are listed in {RULES_DIR_DISPLAY}/{VOCABULARY_FILE}"
                )
                report.warning(f'"{part}" is not an approved {dimension} value; {hint}', line=line)


# --- Package: the files that are published and installed -----------------------


def _extension(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    stem, dot, ext = name.rpartition(".")
    return ext.lower() if dot and stem else None


def _check_package(tree: SkillTree, rules: Rules, findings: list[Finding]) -> None:
    def error(message: str, path: str | None = None) -> None:
        findings.append(Finding("error", message, path))

    for path, entry in sorted(tree.entries.items()):
        if entry.mode == "100755":
            error(
                f'"{path}" is executable; remove the executable bit with '
                f'git update-index --chmod=-x "skills/{tree.name}/{path}"',
                path,
            )
        elif entry.mode == "120000":
            error(f'"{path}" is a symbolic link; a skill must contain only regular files', path)
        elif entry.mode == "160000":
            error(f'"{path}" is a Git submodule; a skill must contain only regular files', path)
        elif entry.mode != REGULAR_FILE_MODE:
            error(f'"{path}" has the unsupported Git mode {entry.mode}', path)

    scripts = next((p for p in sorted(tree.entries) if "scripts" in p.split("/")[:-1]), None)
    if scripts:
        error(
            f'scripts/ folders are not allowed in a skill ("{scripts}"): DevOps Agent rejects them '
            "on upload, and skills are instructions, not code",
            scripts,
        )

    published = published_files(tree, rules)
    if len(published) > MAX_PUBLISHED_FILES:
        error(
            f"the skill has {len(published)} published files; the limit is {MAX_PUBLISHED_FILES}. "
            f"Files under {', '.join(rules.published_excludes)} don't count"
        )

    folded: dict[str, str] = {}
    for path, entry in sorted(published.items()):
        problem = _path_problem(path)
        if problem:
            error(problem, path)
            continue
        other = folded.setdefault(path.casefold(), path)
        if other != path:
            error(f'"{other}" and "{path}" differ only in case, so they collide when the zip is extracted', path)
        ext = _extension(path)
        if ext is None:
            error(f'"{path}" has no file extension; DevOps Agent skill uploads accept only the extensions in skills/.gitignore', path)
        elif ext not in rules.allowed_extensions:
            error(
                f'"{path}" has extension ".{ext}", which DevOps Agent skill uploads don\'t accept; '
                "the allowed extensions are listed in skills/.gitignore",
                path,
            )
        if entry.mode == REGULAR_FILE_MODE and entry.data.startswith(b"#!"):
            error(f'"{path}" starts with #!, which DevOps Agent skill uploads reject', path)

    regular = {p: e.data for p, e in published.items() if e.mode == REGULAR_FILE_MODE}
    zip_bytes = len(build_zip(regular))
    if zip_bytes > ZIP_LIMIT_BYTES:
        error(f"the skill's published files zip to {zip_bytes:,} bytes; the limit is {ZIP_LIMIT_BYTES:,}")
    elif zip_bytes > ZIP_LIMIT_BYTES * ZIP_WARNING_RATIO:
        findings.append(
            Finding(
                "warning",
                f"the skill's published files zip to {zip_bytes:,} bytes, over 90% of the "
                f"{ZIP_LIMIT_BYTES:,}-byte limit",
            )
        )


def _path_problem(path: str) -> str | None:
    if len(path) > MAX_PATH_LENGTH:
        return f'"{path[:60]}…" is {len(path):,} characters long; the limit is {MAX_PATH_LENGTH}'
    for segment in path.split("/"):
        if segment in ("", ".", ".."):
            return f'"{path}" has an empty, "." or ".." part'
        if segment.startswith("."):
            return f'"{path}" is a hidden file or folder ("{segment}"), which would be published; remove it'
        if not SEGMENT_PATTERN.fullmatch(segment):
            return f'"{path}" may use only letters, digits, ".", "_" and "-" in each part of its path'
        if segment.endswith("."):
            return f'"{path}" has a part that ends with a period, which Windows can\'t extract'
        if segment.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
            return f'"{path}" uses the reserved name "{segment.split(".")[0]}", which Windows can\'t extract'
    return None


# --- Content: what must never be public, or hidden from reviewers ---------------


def _line_at(data: bytes | str, index: int) -> int:
    newline = b"\n" if isinstance(data, bytes) else "\n"
    return data.count(newline, 0, index) + 1


def _check_content(tree: SkillTree, rules: Rules, findings: list[Finding]) -> None:
    for path, entry in sorted(tree.entries.items()):
        if entry.mode != REGULAR_FILE_MODE:
            continue
        for match in AWS_ACCESS_KEY_PATTERN.finditer(entry.data):
            if match.group() not in DOCUMENTED_EXAMPLE_KEYS:
                findings.append(
                    Finding(
                        "error",
                        "contains what looks like an AWS access key ID; remove it, and deactivate the key if it is real",
                        path,
                        _line_at(entry.data, match.start()),
                    )
                )
        for match in PRIVATE_KEY_PATTERN.finditer(entry.data):
            findings.append(
                Finding(
                    "error",
                    "contains a private key; remove it, and treat the key as compromised",
                    path,
                    _line_at(entry.data, match.start()),
                )
            )

    for path, entry in sorted(published_files(tree, rules).items()):
        if entry.mode != REGULAR_FILE_MODE or _extension(path) not in TEXT_EXTENSIONS:
            continue
        text = entry.data.decode("utf-8", "replace")
        match = INVISIBLE_PATTERN.search(text)
        if match:
            findings.append(
                Finding(
                    "error",
                    f"contains an invisible character (U+{ord(match.group()):04X}) that can hide text from "
                    "reviewers while the model still reads it; remove it",
                    path,
                    _line_at(text, match.start()),
                )
            )
        if _extension(path) == "md":
            _check_markdown(path, text, findings)


def _check_markdown(path: str, text: str, findings: list[Finding]) -> None:
    def warn(message: str, index: int) -> None:
        findings.append(Finding("warning", message, path, _line_at(text, index)))

    seen: set[str] = set()
    for match in ACTIVE_HTML_PATTERN.finditer(text):
        tag = (match.group(1) or match.group(2)).lower()
        if tag not in seen:
            seen.add(tag)
            warn(f"contains an HTML <{tag}> element; skill previews don't render raw HTML, so use Markdown", match.start())
    if match := JAVASCRIPT_URL_PATTERN.search(text):
        warn("contains a javascript: link; links must use https://", match.start())
    if match := HTTP_LINK_PATTERN.search(text):
        warn("links to an http:// address; use https://", match.start())


# --- Conformance cases ------------------------------------------------------------


def load_cases(path: Path) -> list[dict]:
    """The cases in conformance-cases.json. Raises ValueError when the file is malformed."""
    document = _read_json(path)
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path.name}: expected an object with a non-empty cases list")
    seen: set[str] = set()
    for case in cases:
        problem = _case_problem(case)
        if problem is None and case["id"] in seen:
            problem = "duplicate id"
        if problem:
            raise ValueError(f"{path.name}: case {case.get('id', '?') if isinstance(case, dict) else '?'}: {problem}")
        seen.add(case["id"])
    return cases


def _case_problem(case) -> str | None:
    if not isinstance(case, dict):
        return "a case must be an object"
    for key in ("id", "name", "expect"):
        if not isinstance(case.get(key), str):
            return f'"{key}" must be a string'
    if case["expect"] not in ("pass", "fail"):
        return '"expect" must be "pass" or "fail"'
    if case["expect"] == "fail" and not isinstance(case.get("error"), str):
        return 'a "fail" case needs an "error" string'
    if not isinstance(case.get("files"), dict):
        return '"files" must be an object'
    for path, spec in case["files"].items():
        if not isinstance(spec, dict) or len({"text", "base64"} & set(spec)) != 1:
            return f'file "{path}" needs exactly one of "text" or "base64"'
    return None


def tree_from_files(name: str, files: dict) -> SkillTree:
    """A SkillTree from a case's "files" object: {path: {"text"|"base64": ..., "mode"?: ...}}."""
    entries = {}
    for path, spec in files.items():
        data = spec["text"].encode("utf-8") if "text" in spec else base64.b64decode(spec["base64"])
        entries[path] = Entry(path, spec.get("mode", "100644"), data)
    return SkillTree(name, entries)


def run_conformance(cases: list[dict], rules: Rules) -> list[str]:
    """Problems with the rules' results on the cases; an empty list means every case gives its expected result."""
    problems = []
    for case in cases:
        findings, _ = check_skill(tree_from_files(case["name"], case["files"]), rules)
        errors = [f.message for f in findings if f.severity == "error"]
        if case["expect"] == "pass" and errors:
            problems.append(f"case {case['id']}: expected pass, got: {'; '.join(errors)}")
        elif case["expect"] == "fail" and not any(case["error"] in message for message in errors):
            got = "; ".join(errors) if errors else "no errors"
            problems.append(f"case {case['id']}: expected an error containing {case['error']!r}, got: {got}")
    return problems
