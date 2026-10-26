"""Publishing rules for one skill folder, skills/<name>/.

Every function here works on an in-memory copy of a skill folder, so the same
rules run on Git objects in CI (validate_skills.py), on the cases in
skill-rules/conformance-cases.json, and in the unit tests under tests/.

The rules exist because skills on `main` are published automatically, so every
skill must meet them. See the "Skill Publishing Rules" section of
CONTRIBUTING.md.
"""

from __future__ import annotations

import base64
import difflib
import fnmatch
import hashlib
import html
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
INTERNAL_NAMES_FILE = "internal-names.json"

NAME_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
MAX_NAME_LENGTH = 64
# A skill catalog keeps an index file beside the skill folders, so no skill may take its name.
RESERVED_NAMES = frozenset({"index"})
MAX_DESCRIPTION_LENGTH = 1024
MAX_TITLE_LENGTH = 100
MAX_SUMMARY_LENGTH = 200
MAX_COMPATIBILITY_LENGTH = 500
# The skill evaluation tool's structure test warns above this many body lines.
MAX_BODY_LINES = 500
TIERS = ("aws-managed", "partner-managed")

VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
# At most 10 digits in each part, so a version is at most 32 characters and
# each part is an exact integer in JavaScript as well as in Python.
MAX_VERSION_PART_DIGITS = 10
# The version a new skill starts at.
FIRST_VERSION = (1, 0, 0)
# Read only from a merge-base copy of a skill, so a branch cut while a skill
# still had a two-part version, such as 2.6, can be compared.
TWO_PART_VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")

# Patterns are applied with fullmatch: a `$` would also match before a trailing
# newline, which a YAML block scalar (`version: |`) produces.
#
# GitHub's own rule for usernames: alphanumerics and single hyphens, no leading
# or trailing hyphen, at most 39 characters.
GITHUB_LOGIN_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")

DIMENSION_PREFIX = "aws-devops-agent-skills."
DIMENSIONS = ("agent-types", "aws-services", "technical-domains")
DIMENSION_KEYS = tuple(DIMENSION_PREFIX + d for d in DIMENSIONS)

# agent-types decides which agents load the skill, so its values are the API
# values in agent-types.json, not the catalog vocabulary the other two use.
AGENT_TYPES_DIMENSION = "agent-types"
AGENT_TYPES_KEY = DIMENSION_PREFIX + AGENT_TYPES_DIMENSION
VOCABULARY_DIMENSIONS = tuple(d for d in DIMENSIONS if d != AGENT_TYPES_DIMENSION)
# Loads the skill for every agent, so it can't be combined with another type.
GENERIC_AGENT_TYPE = "GENERIC"

# The Agent Skills specification's frontmatter fields, plus the optional
# display `title`. Anything else is reported as a warning.
TOP_LEVEL_KEYS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools", "title")
# metadata keys this check knows, besides the aws-devops-agent-skills.* dimensions.
# Any other key is a warning, so a typo such as "deprecate" isn't silently ignored.
METADATA_KEYS = ("author", "version", "summary", "deprecated", "tier")
# A misspelling of DIMENSION_PREFIX, such as "aws-devops-agent-skill." or
# "AWS-DevOps-Agent-Skills.", which would silently drop a skill from a filter.
# A key this close to one of DIMENSION_KEYS counts too.
NEAR_DIMENSION_PREFIX = re.compile(r"aws[-_.]?devops[-_.]?agents?[-_.]?skills?[-_.]", re.IGNORECASE)
NEAR_DIMENSION_KEY_CUTOFF = 0.8

# Package limits. A published skill is capped at 100 files, each at most 1 MiB,
# and a 4 MiB zip. Zip sizes vary a little by tool, so the check leaves a 64 KiB
# margin on the zip. It warns once a skill passes 90% of any of the three.
MAX_PUBLISHED_FILES = 100
MAX_FILE_BYTES = 1_048_576
ZIP_LIMIT_BYTES = 4 * 1_048_576 - 65_536
WARNING_RATIO = 0.9
# The frontmatter is capped as well.
MAX_FRONTMATTER_BYTES = 32_768
MAX_PATH_LENGTH = 512
SEGMENT_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(10)} | {f"LPT{i}" for i in range(10)}
)
# Some zip tools silently drop a part with this name.
RESERVED_SEGMENTS = frozenset({"__proto__"})
REGULAR_FILE_MODE = "100644"
TEXT_EXTENSIONS = frozenset({"md", "txt", "json", "yaml", "yml", "xml", "csv", "tsv", "html", "htm", "svg"})
GITIGNORE_EXTENSION_PATTERN = re.compile(r"^!\*\.([A-Za-z0-9]+)\s*$")

# Content that must never be public. Matched on bytes in every file of the
# skill folder, evals included, since the whole repository is public.
AWS_ACCESS_KEY_PATTERN = re.compile(rb"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")
DOCUMENTED_EXAMPLE_KEYS = frozenset({b"AKIA" + b"IOSFODNN7EXAMPLE"})
# PEM and OpenSSH keys, PGP secret key blocks, and PuTTY .ppk files.
PRIVATE_KEY_PATTERN = re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----|PuTTY-User-Key-File-[0-9]+:")

# Characters that render as nothing, or reorder the text around them, so a
# reviewer reading the diff can't see what the model will read: zero-width and
# other invisible characters (soft hyphen, fillers, joiners, and the code points
# Unicode reserves to render as nothing), bidirectional controls, the byte order
# mark, Unicode tags, and variation selectors, which can carry a hidden payload
# one byte per character. U+FE0E and U+FE0F choose text or emoji presentation
# for the character before them, as in an emoji, so only a run of variation
# selectors counts for those two.
#
# Each range above U+FFFF has a character class of its own: some regular
# expression scanners can't read those characters and would take two of them
# in one class for overlapping ranges.
INVISIBLE_PATTERN = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f"
    "\u3164\ufe00-\ufe0d\ufeff\uffa0\ufff0-\ufff8]"
    "|[\U0001bca0-\U0001bca3]|[\U0001d173-\U0001d17a]|[\U000e0000-\U000e0fff]"
    "|[\ufe0e\ufe0f](?=[\u180b-\u180d\u180f\ufe00-\ufe0f]|[\U000e0100-\U000e01ef])"
)

# Markdown that skill previews won't render the way the source reads. Warnings
# only: placeholders such as <object> and HTML comments are common and harmless.
ACTIVE_HTML_PATTERN = re.compile(r"<(script|iframe|embed|form|style|link|meta)\b|<(object|img)\s", re.IGNORECASE)
# Where Markdown takes a link target: an inline link, an autolink, an HTML
# href, or a reference definition, which may be indented, sit in a block quote
# or a list item, and put its target on the next line.
_LINK_TARGET = (
    r"(?:\]\(\s*<?|<|\bhref\s*=\s*[\"']?\s*"
    r"|^[ \t]*(?:(?:>|[-+*]|[0-9]{1,9}[.)])[ \t]*)*\[(?:[^\]\n\\]|\\.)+\]:\s*<?)"
)
# A backslash escape, which Markdown renders as the character alone, and a
# character reference as Markdown reads one (it must end in ";").
_MARKDOWN_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_CHARACTER_REFERENCE = re.compile(r"&(?:#[0-9]{1,8}|#[xX][0-9a-fA-F]{1,8}|[A-Za-z][A-Za-z0-9]{1,31});")
JAVASCRIPT_URL_PATTERN = re.compile(_LINK_TARGET + r"javascript:", re.IGNORECASE | re.MULTILINE)
HTTP_LINK_PATTERN = re.compile(_LINK_TARGET + r"http://", re.IGNORECASE | re.MULTILINE)
# Inside an HTML attribute a numeric character reference needs no ";", so an
# href is also searched with those decoded.
_HTML_CHARACTER_REFERENCE = re.compile(r"&(?:#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[A-Za-z][A-Za-z0-9]{1,31};)")
_HREF = r"\bhref\s*=\s*[\"']?\s*"
JAVASCRIPT_HREF_PATTERN = re.compile(_HREF + r"javascript:", re.IGNORECASE)
HTTP_HREF_PATTERN = re.compile(_HREF + r"http://", re.IGNORECASE)
# <script>, or a namespaced <svg:script>.
SCRIPT_TAG_PATTERN = re.compile(r"<(?:[A-Za-z][\w.-]*:)?script\b", re.IGNORECASE)
SCRIPT_EXTENSIONS = frozenset({"html", "htm", "svg"})

# What the skill evaluation tool writes that must not be committed: its debug
# transcripts (with --debug) and each functional run's metadata, which names
# the AWS account the run used. skills/.gitignore skips both, but git add -f
# gets around it.
DEBUG_FOLDERS = frozenset({"cli_debug", "sdk_debug"})
# Matched at any depth, as skills/.gitignore matches it.
FUNCTIONAL_METADATA_PATTERN = re.compile(r"(?:.*/)?evals/functional/[^/]+/_metadata\.json")

# .gitattributes settings that change the bytes `git archive`, and so GitHub's
# archive of the repository, holds for a file. Skills are published from that
# archive, so a setting that applies under skills/ would make the published
# files differ from the Git objects this check reads.
ARCHIVE_ATTRIBUTES = frozenset({"export-ignore", "export-subst", "ident", "filter", "eol", "text", "crlf", "working-tree-encoding"})
# Line-ending settings that only take effect when a file is committed. On a
# server with Git's default settings they leave archived bytes as stored.
ARCHIVE_NEUTRAL_SETTINGS = frozenset({"text", "text=auto", "eol=lf", "crlf", "crlf=input"})
SKILLS_FOLDER = "skills"
# Git splits a .gitattributes file at newlines only, and a line at these.
GITATTRIBUTES_BLANKS = " \t\r"

# Plain (unquoted) values that PyYAML, a YAML 1.1 parser, reads as text but
# other parsers read as numbers, such as 1e3, 0o17 or 1_0e3.
YAML12_NUMBER_PATTERN = re.compile(
    r"[-+]?(?:0o[0-7_]+|0x[0-9a-fA-F_]+|0b[01_]+"
    r"|(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9_]*[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)?"
    r"|\.(?:inf|Inf|INF))|\.(?:nan|NaN|NAN)"
)
# Characters PyYAML reads as line breaks and YAML 1.2 parsers don't.
YAML11_LINE_BREAK_PATTERN = re.compile("[\x85\u2028\u2029]")

FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(?:(.*?)\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)

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
    # Internal host and tool names (internal-names.json), each a compiled pattern.
    internal_names: tuple[re.Pattern[str], ...] = ()


@dataclass
class SkillInfo:
    """What later rules need from a parsed SKILL.md."""

    name: str
    version: tuple[int, int, int] | None
    metadata: dict[str, str]
    version_line: int | None = None
    deprecated_line: int | None = None
    name_line: int | None = None


def load_rules(rules_dir: Path, gitignore_text: str) -> Rules:
    """Read the rule data files and the extension allowlist in skills/.gitignore.

    Raises ValueError when any of them is malformed, so the check fails closed.
    """
    agent_types = _read_json(rules_dir / AGENT_TYPES_FILE)
    vocabulary = _read_json(rules_dir / VOCABULARY_FILE)
    published = _read_json(rules_dir / PUBLISHED_FILES_FILE)
    internal = _read_json(rules_dir / INTERNAL_NAMES_FILE)
    try:
        excludes = _string_list(published["exclude"], f"{PUBLISHED_FILES_FILE} exclude")
        if not excludes or not all("/" not in e.rstrip("/") for e in excludes):
            raise TypeError(f"{PUBLISHED_FILES_FILE}: exclude must list root-level names, folders ending in /")
        values = _string_list(agent_types["values"], f"{AGENT_TYPES_FILE} values")
        dimensions = vocabulary["values"]
        aliases = vocabulary["aliases"]
        if not isinstance(dimensions, dict) or set(dimensions) != set(VOCABULARY_DIMENSIONS):
            raise TypeError(f"{VOCABULARY_FILE}: values must have exactly the keys {', '.join(VOCABULARY_DIMENSIONS)}")
        if not isinstance(aliases, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and k and v for k, v in aliases.items()
        ):
            raise TypeError(f"{VOCABULARY_FILE}: aliases must map non-empty strings to non-empty strings")
        vocabulary_sets = {
            dim: frozenset(_string_list(dimensions[dim], f"{VOCABULARY_FILE} {dim}")) for dim in VOCABULARY_DIMENSIONS
        }
        return Rules(
            agent_types=frozenset(values),
            vocabulary=vocabulary_sets,
            aliases=dict(aliases),
            allowed_extensions=allowed_extensions_from_gitignore(gitignore_text),
            published_excludes=tuple(excludes),
            internal_names=_internal_name_patterns(internal),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"malformed rule data in {rules_dir}: {exc}") from exc


def _internal_name_patterns(document) -> tuple[re.Pattern[str], ...]:
    """internal-names.json as patterns: each host with any subdomain, each term as a whole word, ignoring case."""
    if not isinstance(document, dict):
        raise TypeError(f"{INTERNAL_NAMES_FILE}: expected an object with hosts and terms")
    hosts = _string_list(document.get("hosts"), f"{INTERNAL_NAMES_FILE} hosts")
    terms = _string_list(document.get("terms"), f"{INTERNAL_NAMES_FILE} terms")
    patterns = [
        re.compile(
            r"(?<![A-Za-z0-9._-])(?:[A-Za-z0-9-]+\.)*" + re.escape(host) + r"(?![A-Za-z0-9_-]|\.[A-Za-z0-9])",
            re.IGNORECASE,
        )
        for host in hosts
    ]
    patterns += [re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE) for term in terms]
    return tuple(patterns)


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
    """`MAJOR.MINOR.PATCH` as a tuple, or None, also when a part has more than MAX_VERSION_PART_DIGITS digits.

    `allow_two_part` also reads `2.6` as 2.6.0.
    """
    match = VERSION_PATTERN.fullmatch(text) or (TWO_PART_VERSION_PATTERN.fullmatch(text) if allow_two_part else None)
    # The digit limit comes first: Python refuses to convert a very long number.
    if not match or any(len(part) > MAX_VERSION_PART_DIGITS for part in match.groups()):
        return None
    parts = [int(part) for part in match.groups()]
    return (parts[0], parts[1], parts[2] if len(parts) == 3 else 0)


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
    return _SCALAR_KINDS.get(node.tag, "a special YAML value")


def _check_skill_md(folder: str, data: bytes, rules: Rules, findings: list[Finding]) -> SkillInfo | None:
    report = _Report(findings)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error("SKILL.md is not valid UTF-8", line=data.count(b"\n", 0, exc.start) + 1)
        return None

    if text.startswith("\ufeff"):
        report.error("SKILL.md starts with a byte order mark (U+FEFF); save it as UTF-8 without one", line=1)
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
    frontmatter = match.group(1) or ""
    size = len(frontmatter.encode("utf-8"))
    if size > MAX_FRONTMATTER_BYTES:
        report.error(f"the frontmatter is {size:,} bytes; the limit is {MAX_FRONTMATTER_BYTES:,}", line=1)
    if "\t" in frontmatter:
        line = frontmatter.count("\n", 0, frontmatter.index("\t")) + 2
        report.error("the frontmatter contains a tab character; use spaces", line=line)
        return None
    if line_break := YAML11_LINE_BREAK_PATTERN.search(frontmatter):
        report.error(
            f"the frontmatter contains U+{ord(line_break.group()):04X}, which YAML parsers disagree on as a line "
            "break; use a newline",
            line=frontmatter.count("\n", 0, line_break.start()) + 2,
        )
        return None

    root = _parse_frontmatter(frontmatter, report)
    if root is None:
        return None
    if not isinstance(root, MappingNode):
        report.error("the frontmatter must be a mapping of keys to values, such as name: my-skill", line=2)
        return None

    top = _mapping_items(root, "", report)
    for key, (key_node, _) in top.items():
        if key not in TOP_LEVEL_KEYS:
            close = difflib.get_close_matches(key, TOP_LEVEL_KEYS, n=1)
            hint = f' (did you mean "{close[0]}"?)' if close else ""
            report.warning(
                f'unknown top-level key "{key}"{hint}; the Agent Skills specification defines '
                "name, description, license, compatibility, metadata and allowed-tools, and this check "
                "also accepts title",
                line=_line(key_node),
            )

    name = _check_name(folder, top, report)
    _check_description(top, report)
    _check_title(top, report)
    _check_spec_text_fields(top, report)
    _check_body_length(text[match.end():], report)

    metadata, version, lines = _check_metadata(top, rules, report)
    return SkillInfo(
        name=name or folder,
        version=version,
        metadata=metadata,
        version_line=lines.get("version"),
        deprecated_line=lines.get("deprecated"),
        name_line=_line(top["name"][0]) if "name" in top else None,
    )


def _parse_frontmatter(frontmatter: str, report: _Report, *, strict: bool = True) -> Node | None:
    """The composed YAML node tree, or None after reporting why the frontmatter can't be read safely.

    With strict=False only PyYAML's own reading applies, for a merge-base copy
    that may predate the stricter rules.
    """
    if not strict:
        try:
            return yaml.compose(frontmatter, Loader=yaml.SafeLoader)
        except (yaml.YAMLError, RecursionError):
            return None
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
    marker = frontmatter.find("---")
    if marker != -1:
        # Some readers end the frontmatter at the first "---", even inside a value.
        report.error(
            'the frontmatter contains "---", which other tools read as its end',
            line=frontmatter.count("\n", 0, marker) + 2,
        )
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
        return None
    if _report_key_problems(root, report):
        return None
    return root


def _report_key_problems(root: Node, report: _Report) -> bool:
    """Report keys, in any mapping at any depth, that parsers could read differently. True if there were any.

    A key must be plain text that no parser reads as a number, true/false or
    null, and must not repeat: PyYAML keeps the last value of a repeated key,
    while other parsers reject the file.
    """
    problems: list[tuple[int, str]] = []
    stack: list[tuple[Node, str]] = [(root, "")]
    while stack:
        node, prefix = stack.pop()
        if isinstance(node, MappingNode):
            seen: set[str] = set()
            for key_node, value_node in node.value:
                if not (
                    isinstance(key_node, ScalarNode)
                    and key_node.tag == STR_TAG
                    and not (key_node.style is None and YAML12_NUMBER_PATTERN.fullmatch(key_node.value))
                ):
                    problems.append((_line(key_node), "frontmatter keys must be plain text"))
                    continue
                if key_node.value in seen:
                    problems.append((_line(key_node), f'duplicate key "{prefix}{key_node.value}"'))
                seen.add(key_node.value)
                stack.append((value_node, f"{prefix}{key_node.value}."))
        elif isinstance(node, SequenceNode):
            stack += [(item, prefix) for item in node.value]
    for line, message in sorted(problems):
        report.error(message, line=line)
    return bool(problems)


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


def _text(items: dict, key: str, label: str, report: _Report, *, required: bool = False) -> str | None:
    """The string value of `key`, or None after reporting that it isn't text. A missing key returns None silently."""
    if key not in items:
        return None
    key_node, value_node = items[key]
    if isinstance(value_node, ScalarNode) and value_node.tag == STR_TAG:
        if value_node.style is None and YAML12_NUMBER_PATTERN.fullmatch(value_node.value):
            report.error(
                f'"{label}" must be text, but other YAML parsers read {value_node.value} as a number. '
                f'Put the value in quotes, for example {key}: "{value_node.value}"',
                line=_line(key_node),
            )
            return None
        return value_node.value
    if isinstance(value_node, ScalarNode) and value_node.tag == "tag:yaml.org,2002:null":
        advice = "give it a value" if required else "give it a value or remove the key"
        report.error(f'"{label}" has no value; {advice}', line=_line(key_node))
        return None
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
    name = _text(top, "name", "name", report, required=True)
    if name is None:
        return None
    line = _line(top["name"][0])
    if len(name) > MAX_NAME_LENGTH:
        report.error(f'"name" is {len(name):,} characters; the limit is {MAX_NAME_LENGTH}', line=line)
    if not NAME_PATTERN.fullmatch(name):
        report.error('"name" must be lowercase letters, digits and single hyphens, such as my-skill', line=line)
    if name in RESERVED_NAMES:
        report.error(f'"name" can\'t be "{name}", which is reserved for the skill catalog\'s index', line=line)
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
    description = _text(top, "description", "description", report, required=True)
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
    if not title.strip():
        report.error('"title" must not be empty; remove it or give it a value', line=line)
    if not _single_line(title):
        report.error('"title" must be a single line', line=line)
    if len(title.strip()) > MAX_TITLE_LENGTH:
        report.error(f'"title" is {len(title.strip()):,} characters; the limit is {MAX_TITLE_LENGTH}', line=line)


def _check_spec_text_fields(top: dict, report: _Report) -> None:
    """license, compatibility and allowed-tools, as the skill evaluation tool's structure test checks them."""
    for key in ("license", "compatibility", "allowed-tools"):
        value = _text(top, key, key, report)
        if value is None:
            continue
        line = _line(top[key][0])
        if not value.strip():
            report.error(f'"{key}" must not be empty; remove it or give it a value', line=line)
        elif key == "compatibility" and len(value) > MAX_COMPATIBILITY_LENGTH:
            report.error(
                f'"compatibility" is {len(value):,} characters; the limit is {MAX_COMPATIBILITY_LENGTH}', line=line
            )


def _check_body_length(body: str, report: _Report) -> None:
    # Counted the way the skill evaluation tool's structure test counts: every
    # piece between newlines, so a final newline adds one.
    lines = len(body.split("\n"))
    if lines > MAX_BODY_LINES:
        report.warning(
            f"the SKILL.md body is {lines:,} lines; the skill evaluation tool warns above {MAX_BODY_LINES}, "
            "so move reference material into references/ and link to it"
        )


def _check_metadata(
    top: dict, rules: Rules, report: _Report
) -> tuple[dict[str, str], tuple[int, int, int] | None, dict[str, int]]:
    """The metadata values, the parsed version, and the SKILL.md line of each value."""
    if "metadata" not in top:
        report.error('"metadata" is required, with at least author and version')
        return {}, None, {}
    key_node, node = top["metadata"]
    metadata_line = _line(key_node)
    if not isinstance(node, MappingNode):
        report.error('"metadata" must be a mapping, with one key: value pair per line', line=metadata_line)
        return {}, None, {}

    items = _mapping_items(node, "metadata.", report)
    metadata: dict[str, str] = {}
    lines: dict[str, int] = {}
    for key in items:
        value = _text(items, key, f"metadata.{key}", report, required=key in ("author", "version"))
        if value is not None:
            metadata[key] = value
            lines[key] = _line(items[key][0])

    _check_unknown_metadata_keys(items, report)
    _check_author(metadata, items, lines, metadata_line, report)
    version = _check_version(metadata, items, lines, metadata_line, report)
    _check_summary(metadata, items, lines, metadata_line, report)
    _check_deprecated(metadata, lines, report)
    _check_tier(metadata, lines, report)
    _check_agent_types(metadata, items, lines, metadata_line, rules, report)
    _check_dimensions(metadata, items, rules, report)
    return metadata, version, lines


def _check_unknown_metadata_keys(items: dict, report: _Report) -> None:
    known = list(METADATA_KEYS) + list(DIMENSION_KEYS)
    for key, (key_node, _) in items.items():
        if key in METADATA_KEYS or key.startswith(DIMENSION_PREFIX):
            continue  # Dimension keys are checked in _check_dimensions.
        if NEAR_DIMENSION_PREFIX.match(key) or difflib.get_close_matches(
            key.lower(), DIMENSION_KEYS, n=1, cutoff=NEAR_DIMENSION_KEY_CUTOFF
        ):
            report.error(
                f'"metadata.{key}" misspells the {DIMENSION_PREFIX} prefix; use one of: '
                + ", ".join(DIMENSION_KEYS),
                line=_line(key_node),
            )
            continue
        close = difflib.get_close_matches(key, known, n=1)
        hint = f'; did you mean "{close[0]}"?' if close else ""
        report.warning(f'unknown metadata key "{key}"{hint}', line=_line(key_node))


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
    text = metadata["version"]
    if not VERSION_PATTERN.fullmatch(text):
        report.error(
            f'"metadata.version" is "{text[:40]}"; it must be MAJOR.MINOR.PATCH, for example "1.2.0", '
            "with no prefix or suffix",
            line=lines["version"],
        )
        return None
    version = parse_version(text)
    if version is None:
        report.error(
            f'"metadata.version" is "{text[:40]}"; each part can have at most {MAX_VERSION_PART_DIGITS} digits',
            line=lines["version"],
        )
    return version


def _check_summary(metadata: dict, items: dict, lines: dict, metadata_line: int, report: _Report) -> None:
    if "summary" in items and "summary" not in metadata:
        return  # _text already reported that it isn't text.
    summary = metadata.get("summary")
    if summary is None or not summary.strip():
        # Becomes an error once every existing skill has a summary.
        report.warning(
            f'"metadata.summary" is {"missing" if summary is None else "empty"}. It will be required once every '
            "skill has one: one line of at most 200 characters, shown as the skill's card text in catalogs",
            line=metadata_line if summary is None else lines["summary"],
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


def _check_tier(metadata: dict, lines: dict, report: _Report) -> None:
    tier = metadata.get("tier")
    if tier is not None and tier not in TIERS:
        report.error(
            '"metadata.tier" must be "aws-managed" or "partner-managed": who maintains the skill',
            line=lines["tier"],
        )


def _check_agent_types(
    metadata: dict, items: dict, lines: dict, metadata_line: int, rules: Rules, report: _Report
) -> None:
    if AGENT_TYPES_KEY in items and AGENT_TYPES_KEY not in metadata:
        return  # _text already reported that it isn't text.
    value = metadata.get(AGENT_TYPES_KEY)
    if value is None:
        report.warning(
            f'"metadata.{AGENT_TYPES_KEY}" is not set, so the skill installs as GENERIC '
            "and loads for every agent. Set it to the agent types the skill is for, for example "
            f'{AGENT_TYPES_KEY}: "INCIDENT_RCA"; '
            f"the values are listed in {RULES_DIR_DISPLAY}/{AGENT_TYPES_FILE}",
            line=metadata_line,
        )
        return
    parts = _split(value)
    for part in parts:
        if not part:
            report.error(
                f'"metadata.{AGENT_TYPES_KEY}" has an empty value between commas',
                line=lines[AGENT_TYPES_KEY],
            )
        elif part not in rules.agent_types:
            report.error(
                f'"metadata.{AGENT_TYPES_KEY}" has unknown value "{part}"; '
                f"allowed values are listed in {RULES_DIR_DISPLAY}/{AGENT_TYPES_FILE}",
                line=lines[AGENT_TYPES_KEY],
            )
    # The Asset API rejects GENERIC alongside another agent type, because GENERIC
    # already loads the skill for every agent.
    if GENERIC_AGENT_TYPE in parts and len(set(parts)) > 1:
        others = ", ".join(sorted(set(parts) - {GENERIC_AGENT_TYPE}))
        report.error(
            f'"metadata.{AGENT_TYPES_KEY}" combines {GENERIC_AGENT_TYPE} with {others}; '
            f"{GENERIC_AGENT_TYPE} already loads the skill for every agent, so it must stand alone. "
            f"List the specific agent types instead, or only {GENERIC_AGENT_TYPE}",
            line=lines[AGENT_TYPES_KEY],
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
        if dimension == AGENT_TYPES_DIMENSION:
            continue  # _check_agent_types validates it against agent-types.json.
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

    debug = next((p for p in sorted(tree.entries) if DEBUG_FOLDERS & {d.lower() for d in p.split("/")[:-1]}), None)
    if debug:
        folder = next(part for part in debug.split("/") if part.lower() in DEBUG_FOLDERS)
        error(
            f'"{debug}" is in a {folder}/ folder, which the skill evaluation tool writes unredacted with --debug; '
            "remove the folder",
            debug,
        )
    for path in sorted(tree.entries):
        if FUNCTIONAL_METADATA_PATTERN.fullmatch(path):
            error(
                f'"{path}" is run metadata from the skill evaluation tool, which names the AWS account the run '
                "used; remove it (skills/.gitignore already skips it)",
                path,
            )

    def warning(message: str, path: str | None = None) -> None:
        findings.append(Finding("warning", message, path))

    published = published_files(tree, rules)
    if len(published) > MAX_PUBLISHED_FILES:
        error(
            f"the skill has {len(published)} published files; the limit is {MAX_PUBLISHED_FILES}. "
            f"Files under {', '.join(rules.published_excludes)} don't count"
        )
    elif len(published) > MAX_PUBLISHED_FILES * WARNING_RATIO:
        warning(f"the skill has {len(published)} published files, over 90% of the limit of {MAX_PUBLISHED_FILES}")

    folded: dict[str, str] = {}
    for path, entry in sorted(published.items()):
        problem = _path_problem(path)
        if problem:
            error(problem, path)
            continue
        other = folded.setdefault(path.casefold(), path)
        if other != path:
            error(f'"{other}" and "{path}" differ only in case, so they collide when the zip is extracted', path)
        if entry.mode != REGULAR_FILE_MODE:
            continue  # Already reported above.
        ext = _extension(path)
        if ext is None:
            error(f'"{path}" has no file extension; DevOps Agent skill uploads accept only the extensions in skills/.gitignore', path)
        elif ext not in rules.allowed_extensions:
            error(
                f'"{path}" has extension ".{ext}", which DevOps Agent skill uploads don\'t accept; '
                "the allowed extensions are listed in skills/.gitignore",
                path,
            )
        if entry.data.startswith(b"#!"):
            error(f'"{path}" starts with #!, which DevOps Agent skill uploads reject', path)
        if len(entry.data) > MAX_FILE_BYTES:
            error(f'"{path}" is {len(entry.data):,} bytes; a published file can be at most {MAX_FILE_BYTES:,}', path)
        elif len(entry.data) > MAX_FILE_BYTES * WARNING_RATIO:
            warning(f'"{path}" is {len(entry.data):,} bytes, over 90% of the {MAX_FILE_BYTES:,}-byte limit', path)
    _check_folder_collisions(sorted(published), error)

    # Paths already reported above are left out, so the zip can always be built.
    regular = {
        p: e.data for p, e in published.items() if e.mode == REGULAR_FILE_MODE and _path_problem(p) is None
    }
    zip_bytes = len(build_zip(regular))
    if zip_bytes > ZIP_LIMIT_BYTES:
        error(f"the skill's published files zip to {zip_bytes:,} bytes; the limit is {ZIP_LIMIT_BYTES:,}")
    elif zip_bytes > ZIP_LIMIT_BYTES * WARNING_RATIO:
        warning(f"the skill's published files zip to {zip_bytes:,} bytes, over 90% of the {ZIP_LIMIT_BYTES:,}-byte limit")


def _check_folder_collisions(paths: list[str], error) -> None:
    """Folders that differ only in case, and a file whose path is also a folder's, in any case."""
    folders: dict[str, str] = {}
    reported: set[str] = set()
    for path in paths:
        parts = path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            folder = "/".join(parts[:depth])
            key = folder.casefold()
            other = folders.setdefault(key, folder)
            if other != folder and key not in reported:
                reported.add(key)
                # Folders inside a colliding pair collide too; report only the outermost.
                if not any(key.startswith(r + "/") for r in reported):
                    error(f'the folders "{other}" and "{folder}" differ only in case, so they collide when extracted', path)
    for path in paths:
        folder = folders.get(path.casefold())
        if folder is not None:
            error(f'"{path}" is a file, but "{folder}/" is a folder; a case-insensitive file system can\'t hold both', path)


def _path_problem(path: str) -> str | None:
    if len(path) > MAX_PATH_LENGTH:
        return f'"{path[:60]}…" is {len(path):,} characters long; the limit is {MAX_PATH_LENGTH}'
    for segment in path.split("/"):
        if segment in ("", ".", ".."):
            return f'"{path}" has an empty, "." or ".." part'
        if segment.startswith("."):
            return f'"{path}" is a hidden file or folder ("{segment}"), which would be published; remove it'
        if segment in RESERVED_SEGMENTS:
            return f'"{path}" has a part named "{segment}", which some zip tools silently drop'
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
        # A byte order mark at the start of SKILL.md is reported with its frontmatter.
        start = 1 if path == "SKILL.md" and text.startswith("\ufeff") else 0
        match = INVISIBLE_PATTERN.search(text, start)
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
        if len(entry.data) > MAX_FILE_BYTES:
            continue  # Already an error; not worth scanning further.
        if _extension(path) == "md":
            _check_markdown(path, text, findings)
        elif _extension(path) in SCRIPT_EXTENSIONS and (script := SCRIPT_TAG_PATTERN.search(text)):
            findings.append(
                Finding(
                    "warning",
                    "contains a <script> element; a skill holds instructions and templates, not code, so remove it",
                    path,
                    _line_at(text, script.start()),
                )
            )


def _lines(data: bytes) -> list[str]:
    """Lines as GitHub numbers them: split at newlines only, each without a trailing carriage return."""
    return [line.removesuffix("\r") for line in data.decode("utf-8", "replace").split("\n")]


def check_added_content(base: SkillTree | None, head: SkillTree, rules: Rules) -> list[Finding]:
    """Warnings for internal host or tool names on lines the pull request adds, in any file of the skill.

    Only added lines count, as in scan-aws-identifiers, so names already on the
    base branch don't warn on every pull request that touches the skill. A line
    that any file of the skill held on the base branch isn't added, so moving a
    file doesn't warn either.
    """
    findings: list[Finding] = []
    base_entries = base.entries if base is not None else {}
    changed = [
        (path, entry)
        for path, entry in sorted(head.entries.items())
        if entry.mode == REGULAR_FILE_MODE
        and not (path in base_entries and base_entries[path].data == entry.data)
    ]
    if not changed:
        return findings
    old_lines = {
        line for entry in base_entries.values() if entry.mode == REGULAR_FILE_MODE for line in _lines(entry.data)
    }
    for path, entry in changed:
        hits = []
        for number, line in enumerate(_lines(entry.data), 1):
            if line in old_lines:
                continue
            match = next((m for pattern in rules.internal_names if (m := pattern.search(line))), None)
            if match:
                hits.append((number, match.group()))
        if hits:
            number, name = hits[0]
            more = f", and {len(hits) - 1} more line(s) like it" if len(hits) > 1 else ""
            findings.append(
                Finding(
                    "warning",
                    f'adds "{name}", an internal host or tool name{more}; this repository is public, so remove it',
                    path,
                    number,
                )
            )
    return findings


def gitattributes_line_applies_to_skills(line: str) -> bool:
    """Whether one line of the root .gitattributes can change archived bytes under skills/.

    It errs toward yes. A macro definition counts when it sets an archive
    attribute, since the macro can then be used on any pattern, and a pattern
    this function can't read exactly is taken to match skills/.
    """
    line = line.strip(GITATTRIBUTES_BLANKS)
    if not line or line.startswith("#"):
        return False
    if line.startswith('"'):
        # A C-style quoted pattern, which may contain spaces.
        quoted = re.match(r'"((?:[^"\\]|\\.)*)"', line)
        if quoted is None:
            return _sets_archive_attribute(_gitattributes_tokens(line)[1:])
        pattern, rest = quoted[1], line[quoted.end():]
    else:
        pattern, *more = re.split(f"[{GITATTRIBUTES_BLANKS}]+", line, maxsplit=1)
        rest = more[0] if more else ""
    if not _sets_archive_attribute(_gitattributes_tokens(rest)):
        return False
    if pattern.startswith("[attr]"):
        return True
    if pattern.startswith("!"):
        return False  # Git ignores negative patterns in .gitattributes.
    anchored = pattern.startswith("/")
    first, slash, _ = pattern.lstrip("/").rstrip("/").partition("/")
    if anchored or slash:
        # Matched from the root, so its first part must match the skills folder.
        # Without a further slash only that folder itself matches, which
        # export-ignore drops whole.
        return _part_may_match(first, SKILLS_FOLDER)
    return True  # Matched at any depth, so under skills/ too.


def _gitattributes_tokens(text: str) -> list[str]:
    return [token for token in re.split(f"[{GITATTRIBUTES_BLANKS}]+", text) if token]


def _sets_archive_attribute(tokens: list[str]) -> bool:
    return any(
        not token.startswith(("-", "!"))
        and token not in ARCHIVE_NEUTRAL_SETTINGS
        and token.split("=", 1)[0] in ARCHIVE_ATTRIBUTES
        for token in tokens
    )


def _part_may_match(pattern: str, name: str) -> bool:
    """Whether one part of a .gitattributes pattern can match `name`. Brackets and backslashes count as a match."""
    if "[" in pattern or "\\" in pattern:
        return True
    return fnmatch.fnmatchcase(name, pattern)


def _check_markdown(path: str, text: str, findings: list[Finding]) -> None:
    def warn(message: str, index: int) -> None:
        findings.append(Finding("warning", message, path, _line_at(text, index)))

    seen: set[str] = set()
    for match in ACTIVE_HTML_PATTERN.finditer(text):
        tag = (match.group(1) or match.group(2)).lower()
        if tag not in seen:
            seen.add(tag)
            warn(f"contains an HTML <{tag}> element; skill previews don't render raw HTML, so use Markdown", match.start())
    # Character references and backslash escapes can spell a scheme Markdown
    # still renders as a link, so the decoded text is searched too. A decoded
    # newline stays a space, so line numbers still match the file.
    def decode(pattern: re.Pattern[str], source: str) -> str:
        return pattern.sub(lambda m: html.unescape(m[0]).replace("\n", " "), source)

    decoded = _MARKDOWN_ESCAPE.sub(r"\1", decode(_CHARACTER_REFERENCE, text))
    html_decoded: str | None = None
    for pattern, href_pattern, message in (
        (JAVASCRIPT_URL_PATTERN, JAVASCRIPT_HREF_PATTERN, "contains a javascript: link; links must use https://"),
        (HTTP_LINK_PATTERN, HTTP_HREF_PATTERN, "links to an http:// address; use https://"),
    ):
        source, match = text, pattern.search(text)
        if match is None:
            source, match = decoded, pattern.search(decoded)
        if match is None:
            html_decoded = html_decoded if html_decoded is not None else decode(_HTML_CHARACTER_REFERENCE, text)
            source, match = html_decoded, href_pattern.search(html_decoded)
        if match:
            findings.append(Finding("warning", message, path, _line_at(source, match.start())))


# --- History: identity and versions against the merge base --------------------


def content_hash(files: dict[str, bytes]) -> str:
    """The skill content hash: SHA-256 over sorted `<path>\\0<sha256 hex of the file>\\n` records.

    Any other tool that computes it must give the same result; the golden
    fixture in conformance-cases.json pins the function.
    """
    outer = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.encode("utf-8", "surrogateescape")):
        digest = hashlib.sha256(files[path]).hexdigest()
        outer.update(path.encode("utf-8", "surrogateescape") + b"\0" + digest.encode("ascii") + b"\n")
    return outer.hexdigest()


def published_hash(tree: SkillTree, rules: Rules) -> str:
    return content_hash({p: e.data for p, e in published_files(tree, rules).items()})


def _format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def _next_versions(version: tuple[int, int, int]) -> tuple[tuple[int, int, int], ...]:
    """The only versions allowed after `version`: the next patch, minor or major release."""
    major, minor, patch = version
    return ((major, minor, patch + 1), (major, minor + 1, 0), (major + 1, 0, 0))


def _lenient_version(tree: SkillTree) -> tuple[int, int, int] | None:
    """The merge-base copy's version, reading a two-part version such as 2.6 as 2.6.0. None if unreadable.

    Fixing a two-part version changes SKILL.md, so the fix itself needs a
    version above the old one: 2.6 -> 2.6.1, not 2.6.0.
    """
    entry = tree.entries.get("SKILL.md")
    try:
        match = FRONTMATTER_PATTERN.match(entry.data.decode("utf-8")) if entry else None
    except UnicodeDecodeError:
        return None
    scratch = _Report([])
    root = _parse_frontmatter(match.group(1) or "", scratch, strict=False) if match else None
    metadata = _last_value(root, "metadata")
    node = _last_value(metadata, "version")
    if isinstance(node, ScalarNode) and node.tag == STR_TAG:
        return parse_version(node.value, allow_two_part=True)
    return None


def _last_value(node: Node | None, key: str) -> Node | None:
    """The value of `key` in a mapping node, the last one if it repeats, as PyYAML reads it."""
    found = None
    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            if isinstance(key_node, ScalarNode) and key_node.tag == STR_TAG and key_node.value == key:
                found = value_node
    return found


def check_history(
    name: str, base: SkillTree | None, head: SkillTree | None, rules: Rules, retired: frozenset[str]
) -> list[Finding]:
    """The rules that compare a skill with its merge-base copy. `retired` holds paths of skills removed earlier."""
    if base is not None and head is None:
        return [
            Finding(
                "error",
                f"the skill folder skills/{name} was removed. A skill's folder is its permanent identity, "
                'so a skill is never removed, even in an emergency: set metadata.deprecated: "true" instead. '
                "To rename a skill, deprecate this folder and add the new one",
            )
        ]
    if head is None:
        return []
    if base is None:
        info = check_skill(head, rules)[1]
        if name in retired:
            return [
                Finding(
                    "error",
                    f"skills/{name} was used by a skill that was removed earlier, and a skill path is never "
                    "reused, because installed copies still point at it. Choose a new name",
                    "SKILL.md" if "SKILL.md" in head.entries else None,
                    info.name_line if info is not None else None,
                )
            ]
        if info is not None and info.version is not None and info.version != FIRST_VERSION:
            message = f"a new skill starts at version 1.0.0, not {_format_version(info.version)}"
            return [Finding("error", message, "SKILL.md", info.version_line)]
        return []

    head_info = check_skill(head, rules)[1]
    if head_info is None or head_info.version is None:
        return []  # check_skill already reports why the head version is unusable.
    old = _lenient_version(base)
    if old is None:
        return [
            Finding(
                "warning",
                "the version rules were not checked, because the version on the base branch can't be read",
                "SKILL.md",
                head_info.version_line,
            )
        ]
    new = head_info.version
    changed = published_hash(base, rules) != published_hash(head, rules)
    if new < old:
        message = f"metadata.version went down from {_format_version(old)} to {_format_version(new)}; it must never go down"
        return [Finding("error", message, "SKILL.md", head_info.version_line)]
    if new == old and changed:
        message = (
            f"published files changed, so metadata.version must go up from {_format_version(old)}. "
            f"A published version is immutable. Changes only to {', '.join(rules.published_excludes)} need no bump"
        )
        return [Finding("error", message, "SKILL.md", head_info.version_line)]
    if new > old and new not in _next_versions(old):
        steps = [_format_version(v) for v in _next_versions(old)]
        message = (
            f"metadata.version can only go up one step from {_format_version(old)}: to {steps[0]}, {steps[1]} "
            f"or {steps[2]}, not {_format_version(new)}"
        )
        return [Finding("error", message, "SKILL.md", head_info.version_line)]
    if new > old:
        before = base.entries.get("CHANGELOG.md")
        after = head.entries.get("CHANGELOG.md")
        if after is None or (before is not None and before.data == after.data):
            message = f"metadata.version went up to {_format_version(new)}, but CHANGELOG.md has no new entry for it"
            return [Finding("warning", message, "CHANGELOG.md")]
    return []


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
    if "base" in case and case["base"] is not None and not isinstance(case["base"], dict):
        return '"base" must be an object of files, or null for a skill the pull request adds'
    if "retired" in case and not isinstance(case["retired"], bool):
        return '"retired" must be true or false'
    files = case.get("files")
    if files is None and isinstance(case.get("base"), dict):
        pass  # The pull request removes the skill folder.
    elif not isinstance(files, dict):
        return '"files" must be an object (or null, with "base", for a removed folder)'
    for group in (files or {}, case.get("base") or {}):
        problem = _files_problem(group)
        if problem:
            return problem
    return None


def _files_problem(files: dict) -> str | None:
    for path, spec in files.items():
        if not isinstance(spec, dict) or len({"text", "base64"} & set(spec)) != 1:
            return f'file "{path}" needs exactly one of "text" or "base64"'
    return None


def load_golden_hash(path: Path) -> tuple[dict[str, bytes], str]:
    """The golden content-hash fixture: its files and the hash every implementation must compute."""
    document = _read_json(path)
    golden = document.get("content_hash") if isinstance(document, dict) else None
    if not isinstance(golden, dict) or not isinstance(golden.get("sha256"), str):
        raise ValueError(f"{path.name}: expected a content_hash object with files and sha256")
    files = golden.get("files")
    if not isinstance(files, dict) or _files_problem(files):
        raise ValueError(f"{path.name}: content_hash.files is malformed")
    tree = tree_from_files("golden", files)
    return {p: e.data for p, e in tree.entries.items()}, golden["sha256"]


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
        name = case["name"]
        head = tree_from_files(name, case["files"]) if case.get("files") is not None else None
        findings = check_skill(head, rules)[0] if head is not None else []
        if "base" in case or case.get("retired"):
            base = tree_from_files(name, case["base"]) if case.get("base") is not None else None
            retired = frozenset({name}) if case.get("retired") else frozenset()
            findings += check_history(name, base, head, rules, retired)
        errors = [f.message for f in findings if f.severity == "error"]
        if case["expect"] == "pass" and errors:
            problems.append(f"case {case['id']}: expected pass, got: {'; '.join(errors)}")
        elif case["expect"] == "fail" and not any(case["error"] in message for message in errors):
            got = "; ".join(errors) if errors else "no errors"
            problems.append(f"case {case['id']}: expected an error containing {case['error']!r}, got: {got}")
    return problems
