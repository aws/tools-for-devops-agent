#!/usr/bin/env python3
"""Validate that every skill in this repository can be published.

Skills on ``main`` are published as one set: when one skill breaks a rule
below, no skill is published. This check therefore validates every skill
folder under ``skills/`` at the head, not only the folders that a pull request
touches, and reports every error of every skill.

Each skill folder is read with ``git archive``, so the bytes are the bytes of
the published archive of the commit. The published file set of a skill is
every file of its folder except ``evals/`` at the skill root, and
``.skilleval.yaml`` and ``CHANGELOG.md`` at the skill root.

Rules for every skill folder at the head:

  * no symlink, hard link, absolute name, or empty, ``.`` or ``..`` segment
    anywhere under ``skills/``;
  * ``SKILL.md`` exists, is valid UTF-8 (a leading byte order mark is
    allowed), and starts with a ``---`` frontmatter block;
  * the frontmatter is YAML in a safe subset: no anchors, aliases, explicit
    tags, directives, document markers, second document, map keys that are
    not scalars, tabs in indentation, duplicate keys, comments without white
    space before them, block scalar indicators on their own line, keep (``+``)
    chomping, or line breaks other than LF and CRLF;
  * ``name`` is a string of 1 to 64 characters that matches
    ``^[a-z0-9]+(-[a-z0-9]+)*$`` and equals the folder name;
  * ``description`` is a string of 1 to 1024 characters (UTF-16 code units);
  * ``metadata.version`` is a ``MAJOR.MINOR.PATCH`` string. A skill that the
    pull request does not touch can still have a two-part ``MAJOR.MINOR``,
    read as ``MAJOR.MINOR.0``. Remove that allowance when no skill on
    ``main`` has a two-part version;
  * ``metadata.deprecated`` is a boolean, if present;
  * at most 100 published files, each path at most 512 characters and
    matching ``^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$``;
  * the published files are at most 64 MiB in total;
  * the zip of the published files is at most 983,040 bytes: 1 MiB minus a
    64 KiB safety margin, because zip sizes vary by tool. A warning shows
    above 90% of that limit.

The archive of the head commit must also stay at most 128 MiB, and at most
32 MiB when compressed with gzip.

A published version is immutable. Thus, for every skill folder at the merge
base:

  * the folder must still exist at the head (deprecate a skill instead);
  * ``metadata.version`` must not go down;
  * a changed skill content hash needs a higher ``metadata.version``;
  * an unchanged skill content hash must keep the same ``metadata.version``.

The skill content hash is SHA-256 over one record per published file, sorted
by the UTF-8 bytes of the path: the path, a 0x00 byte, the lowercase hex
SHA-256 of the file bytes, and a 0x0A byte.

Frontmatter values are typed like JSON only when the YAML scalar is plain and
the conversion loses nothing: ``true``/``false``, ``null``/``~``/empty, and
numbers that print back as the same text (``3``, ``1.5``). Any other value is
a string (``1.10``, ``2.0``, ``-0``, ``010``, ``2.6.0``). Thus an unquoted
``version: 2.6`` is a number and fails.

Before it checks a skill, the script checks itself: the skill content hash
of a golden fixture, the SHA-256 of ``conformance/cases.json`` against
``CONFORMANCE_SHA256``, and the result of every case in that file. A change
to the corpus must therefore also change ``CONFORMANCE_SHA256`` and
``conformance/README.md``. Run ``--self-check-only`` to check only that.

Exit code is 0 when there is no error, 1 when a skill breaks a rule, and 2
when the self-check fails (then no skill is checked).
"""

from __future__ import annotations

import argparse
import base64
import decimal
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from yaml.composer import Composer
from yaml.events import (
    AliasEvent,
    CollectionStartEvent,
    DocumentEndEvent,
    DocumentStartEvent,
    ScalarEvent,
)
from yaml.nodes import MappingNode, ScalarNode, SequenceNode
from yaml.parser import Parser
from yaml.reader import Reader
from yaml.resolver import BaseResolver
from yaml.scanner import Scanner, ScannerError

SKILLS_DIR = "skills"

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_FILE_COUNT = 100
MAX_PATH_LENGTH = 512
MAX_ZIP_BYTES = 1_048_576
ZIP_MARGIN_BYTES = 65_536
ZIP_LIMIT_BYTES = MAX_ZIP_BYTES - ZIP_MARGIN_BYTES
ZIP_WARNING_RATIO = 0.9
MAX_SKILL_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_COMPRESSED_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_SAFE_INTEGER = 2**53 - 1

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PATH_PATTERN = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
TWO_PART_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
INTEGER_PATTERN = re.compile(r"^-?(0|[1-9][0-9]*)$")
DECIMAL_PATTERN = re.compile(r"^-?(0|[1-9][0-9]*)\.[0-9]+$")
# \Z, not $: the frontmatter block ends at the end of the text, not before a final newline.
FRONTMATTER_PATTERN = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|\Z)")
EXCLUDED_ROOT_FILES = frozenset({".skilleval.yaml", "CHANGELOG.md"})

NAME_PATTERN_SOURCE = "^[a-z0-9]+(-[a-z0-9]+)*$"
PATH_PATTERN_SOURCE = "^[A-Za-z0-9._-]+(\\/[A-Za-z0-9._-]+)*$"

REMOVED_MESSAGE = (
    "a pull request cannot remove a skill folder; set metadata.deprecated: true "
    "and bump metadata.version"
)
HASH_CHANGED_MESSAGE = "published content changed, so metadata.version must go up"
VERSION_ONLY_MESSAGE = "metadata.version changed, but the published content did not"

DOCS_HINT = 'See the "Publishing Rules" section of CONTRIBUTING.md.'

_MISSING = object()

GOLDEN_FILES = {
    "SKILL.md": b"---\nname: example-skill\ndescription: Example skill for the content hash golden test.\nmetadata:\n  version: 1.0.0\n---\n\n# Example\n",
    "references/guide.md": b"Line one\r\nLine two\n",
    "images/pixel.png": bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0xFF]),
    "assets/empty.txt": b"",
}
GOLDEN_HASH = "15f2eecb8d833caa6da288791f742204460d998c6a0d3cfbdb8bc5b51cf01822"

CONFORMANCE_FILE = Path(__file__).resolve().parent / "conformance" / "cases.json"
CONFORMANCE_SHA256 = "df26439cc6d8f5c7eb74250b6ab5ca512ca6f6902464c8affc30b3b82ac7ed2e"
CASE_FIELDS = frozenset({"id", "name", "files", "expect", "error", "stricter"})


class FrontmatterError(ValueError):
    pass


def unsupported(feature: str) -> FrontmatterError:
    return FrontmatterError(
        f"SKILL.md frontmatter uses {feature}, which skills in this repository must not use"
    )


@dataclass
class SkillTree:
    """The regular files of one skill folder at one revision, and its unsafe entries."""

    files: dict[str, bytes] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class HeadResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    version: tuple[int, int, int] | None = None


@dataclass
class SkillReport:
    path: str
    change: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    base_version: str | None = None
    head_version: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def notable(self) -> bool:
        return self.change != "unchanged" or bool(self.errors or self.warnings)


class _FrontmatterLoader(Reader, Scanner, Parser, Composer, BaseResolver):
    """PyYAML without a constructor, and with the YAML 1.2 indentation rules that PyYAML does not apply.

    A flow collection or a multi-line quoted scalar inside a block collection
    must be indented more than that block collection, and a lone ``-`` inside
    a flow collection is a block sequence entry, not a plain scalar.
    """

    def __init__(self, stream: str):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        BaseResolver.__init__(self)

    def _line_indent(self) -> int | None:
        """Leading spaces of the line, or None when text comes before the scanner on that line."""
        prefix = self.buffer[self.pointer - self.column : self.pointer]
        if prefix.strip(" \t"):
            return None
        return len(prefix) - len(prefix.lstrip(" "))

    def _check_flow_line(self) -> None:
        if not self.flow_level or self.peek() in "]}#\0":
            return
        spaces = self._line_indent()
        if spaces is not None and spaces <= self.indent:
            raise ScannerError(
                None,
                None,
                "Flow collection in block collection must be sufficiently indented",
                self.get_mark(),
            )

    def unwind_indent(self, column):
        self._check_flow_line()
        super().unwind_indent(column)

    def scan_plain_spaces(self, indent, start_mark):
        line = self.line
        chunks = super().scan_plain_spaces(indent, start_mark)
        if self.line != line:
            self._check_flow_line()
        return chunks

    def scan_plain(self):
        token = super().scan_plain()
        if self.flow_level and token.value == "-":
            raise ScannerError(
                None,
                None,
                "Block collections are not allowed within flow collections",
                token.start_mark,
            )
        return token

    def scan_to_next_token(self):
        if self.peek() == "#" and self.pointer > 0 and self.buffer[self.pointer - 1] not in " \t\r\n\ufeff":
            raise ScannerError(
                None,
                None,
                "Comments must be separated from other tokens by white space",
                self.get_mark(),
            )
        return super().scan_to_next_token()

    def scan_block_scalar(self, style):
        if self._line_indent() is not None:
            raise ScannerError(
                None,
                None,
                "a block scalar indicator must be on the line of its key",
                self.get_mark(),
            )
        return super().scan_block_scalar(style)

    def scan_block_scalar_indicators(self, start_mark):
        chomping, increment = super().scan_block_scalar_indicators(start_mark)
        if chomping is True:
            raise unsupported("a keep (+) chomping indicator")
        return chomping, increment

    def scan_flow_scalar_breaks(self, double, start_mark):
        chunks = super().scan_flow_scalar_breaks(double, start_mark)
        spaces = self._line_indent()
        if spaces is not None and spaces <= self.indent:
            raise ScannerError(
                "while scanning a quoted scalar",
                start_mark,
                "a line of a multi-line quoted scalar must be indented more than its block collection",
                self.get_mark(),
            )
        return chunks

    def compose_scalar_node(self, anchor):
        event = self.peek_event()
        node = super().compose_scalar_node(anchor)
        node.plain = event.tag is None and event.style is None
        return node


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _check_safe_subset(text: str) -> None:
    if re.search("\r(?!\n)|[\x85\u2028\u2029]", text):
        raise unsupported("a line break character")
    for line in text.split("\n"):
        indentation = line[: len(line) - len(line.lstrip(" \t"))]
        if "\t" in indentation:
            raise unsupported("a tab in indentation")
        if line.startswith("%"):
            raise unsupported("a YAML directive")
    loader = _FrontmatterLoader(text)
    documents = 0
    try:
        while loader.check_event():
            event = loader.get_event()
            if isinstance(event, AliasEvent):
                raise unsupported("an alias")
            if isinstance(event, (ScalarEvent, CollectionStartEvent)):
                if event.anchor is not None:
                    raise unsupported("an anchor")
                if event.tag is not None:
                    raise unsupported("an explicit tag")
            if isinstance(event, DocumentStartEvent):
                documents += 1
                if documents > 1:
                    raise unsupported("more than one document")
                if event.version is not None or event.tags:
                    raise unsupported("a YAML directive")
                if event.explicit:
                    raise unsupported("a document marker")
            if isinstance(event, DocumentEndEvent) and event.explicit:
                raise unsupported("a document marker")
    finally:
        loader.dispose()


def _check_duplicate_keys(node) -> None:
    if isinstance(node, SequenceNode):
        for item in node.value:
            _check_duplicate_keys(item)
    elif isinstance(node, MappingNode):
        keys: set[str] = set()
        for key, value in node.value:
            if isinstance(key, ScalarNode):
                if key.value in keys:
                    raise FrontmatterError("Map keys must be unique")
                keys.add(key.value)
            _check_duplicate_keys(key)
            _check_duplicate_keys(value)


def js_number_text(value: float) -> str:
    """JavaScript String(value) of a finite number, so that "prints back as the same text" matches JSON tools."""
    if value == 0:
        return "0"
    _, digit_tuple, exponent = decimal.Decimal(repr(abs(value))).normalize().as_tuple()
    digits = "".join(map(str, digit_tuple))
    k = len(digits)
    n = exponent + k
    sign = "-" if value < 0 else ""
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * -n + digits
    e = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{sign}{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def plain_scalar_to_json(text: str):
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~", ""):
        return None
    if INTEGER_PATTERN.match(text):
        value = int(text)
        if text != "-0" and abs(value) <= MAX_SAFE_INTEGER:
            return value
    elif DECIMAL_PATTERN.match(text):
        number = float(text)
        if math.isfinite(number) and js_number_text(number) == text:
            return number
    return text


def _to_json(node):
    if isinstance(node, ScalarNode):
        return plain_scalar_to_json(node.value) if node.plain else node.value
    if isinstance(node, SequenceNode):
        return [_to_json(item) for item in node.value]
    result = {}
    for key, value in node.value:
        if not isinstance(key, ScalarNode):
            raise unsupported("a map key that is not a scalar")
        result[key.value] = _to_json(value)
    return result


def parse_frontmatter(text: str) -> dict:
    """Parses the SKILL.md frontmatter to JSON values, or raises FrontmatterError."""
    match = FRONTMATTER_PATTERN.match(text.removeprefix("\ufeff"))
    if match is None:
        raise FrontmatterError("SKILL.md does not start with a --- frontmatter block")
    # Parsed with a final newline, so a block scalar as the last key ends with a newline.
    source = match.group(1) + "\n"
    try:
        _check_safe_subset(source)
        loader = _FrontmatterLoader(source)
        try:
            root = loader.get_single_node()
        finally:
            loader.dispose()
        if root is not None:
            _check_duplicate_keys(root)
        parsed = None if root is None else _to_json(root)
    except (yaml.YAMLError, RecursionError) as exc:
        reason = "nesting is too deep" if isinstance(exc, RecursionError) else _one_line(str(exc))
        raise FrontmatterError(f"SKILL.md frontmatter is not valid YAML: {reason}") from exc
    except FrontmatterError as exc:
        if str(exc).startswith("SKILL.md"):
            raise
        raise FrontmatterError(f"SKILL.md frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise FrontmatterError("SKILL.md frontmatter is not an object")
    return parsed


def decode_skill_md(data: bytes) -> str:
    """Strict UTF-8 that drops one leading byte order mark; parse_frontmatter drops one more."""
    return data.decode("utf-8").removeprefix("\ufeff")


def js_length(text: str) -> int:
    """String length in UTF-16 code units."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def is_published_path(path: str) -> bool:
    return not path.startswith("evals/") and path not in EXCLUDED_ROOT_FILES


def published_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: data for path, data in files.items() if is_published_path(path)}


def sorted_paths(files) -> list[str]:
    return sorted(files, key=lambda path: path.encode("utf-8", "surrogateescape"))


def content_hash(files: dict[str, bytes]) -> str:
    """The skill content hash of a published file set."""
    outer = hashlib.sha256()
    for path in sorted_paths(files):
        digest = hashlib.sha256(files[path]).hexdigest()
        outer.update(path.encode("utf-8", "surrogateescape") + b"\0" + digest.encode("ascii") + b"\n")
    return outer.hexdigest()


def build_zip(files: dict[str, bytes]) -> bytes:
    """Entries sorted by UTF-8 path, deflate level 6, all dated 1980-01-01."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted_paths(files):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[path], compresslevel=6)
    return buffer.getvalue()


def read_version(frontmatter: dict, allow_two_part: bool) -> tuple[int, int, int]:
    metadata = frontmatter.get("metadata")
    version = metadata.get("version") if isinstance(metadata, dict) else None
    if not isinstance(version, str):
        raise FrontmatterError("metadata.version must be a string")
    if allow_two_part and TWO_PART_VERSION_PATTERN.match(version):
        version += ".0"
    if not VERSION_PATTERN.match(version):
        raise FrontmatterError(f"metadata.version {version} must be MAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def _field_errors(name: str, frontmatter: dict) -> list[str]:
    errors = []
    declared = frontmatter.get("name")
    if not isinstance(declared, str) or not 1 <= js_length(declared) <= MAX_NAME_LENGTH:
        errors.append(f"name must be a string of 1 to {MAX_NAME_LENGTH} characters")
    elif not NAME_PATTERN.match(declared):
        errors.append(f"name must match {NAME_PATTERN_SOURCE}")
    elif declared != name:
        errors.append("name must equal the folder name")
    description = frontmatter.get("description")
    if (
        not isinstance(description, str)
        or not 1 <= js_length(description) <= MAX_DESCRIPTION_LENGTH
    ):
        errors.append(
            f"description must be a string of 1 to {MAX_DESCRIPTION_LENGTH} characters"
        )
    return errors


def _path_errors(paths: list[str]) -> list[str]:
    errors = []
    if len(paths) > MAX_FILE_COUNT:
        errors.append(f"skill has {len(paths)} files; the maximum is {MAX_FILE_COUNT}")
    for path in paths:
        if js_length(path) > MAX_PATH_LENGTH:
            errors.append(f"path {path} is longer than {MAX_PATH_LENGTH} characters")
        elif not PATH_PATTERN.match(path):
            errors.append(f"path {path} must match {PATH_PATTERN_SOURCE}")
    return errors


def _size_errors(published: dict[str, bytes], result: HeadResult) -> None:
    total = sum(len(data) for data in published.values())
    if total > MAX_SKILL_BYTES:
        result.errors.append(
            f"published files are {total} bytes in total; the maximum is {MAX_SKILL_BYTES}"
        )
        return
    zip_bytes = len(build_zip(published))
    if zip_bytes > ZIP_LIMIT_BYTES:
        result.errors.append(
            f"zip is {zip_bytes} bytes; the maximum is {ZIP_LIMIT_BYTES} "
            f"(1 MiB minus a {ZIP_MARGIN_BYTES}-byte safety margin, because zip sizes vary by tool)"
        )
    elif zip_bytes > ZIP_LIMIT_BYTES * ZIP_WARNING_RATIO:
        result.warnings.append(
            f"zip is {zip_bytes} bytes, over {int(ZIP_WARNING_RATIO * 100)}% of "
            f"the maximum of {ZIP_LIMIT_BYTES}"
        )


def check_head(name: str, files: dict[str, bytes], strict_version: bool = True) -> HeadResult:
    """The head rules for one skill folder. All errors are reported, not only the first."""
    result = HeadResult()
    published = published_files(files)
    skill_md = published.get("SKILL.md")
    if skill_md is None:
        result.errors.append("SKILL.md is missing")
    else:
        try:
            frontmatter = parse_frontmatter(decode_skill_md(skill_md))
        except UnicodeDecodeError:
            result.errors.append("SKILL.md is not valid UTF-8")
        except FrontmatterError as exc:
            result.errors.append(str(exc))
        else:
            result.errors += _field_errors(name, frontmatter)
            try:
                result.version = read_version(frontmatter, allow_two_part=not strict_version)
            except FrontmatterError as exc:
                result.errors.append(str(exc))
            metadata = frontmatter.get("metadata")
            deprecated = metadata.get("deprecated", _MISSING) if isinstance(metadata, dict) else _MISSING
            if deprecated is not _MISSING and not isinstance(deprecated, bool):
                result.errors.append("metadata.deprecated must be a boolean")
    result.errors += _path_errors(sorted_paths(published))
    _size_errors(published, result)
    return result


def base_version(files: dict[str, bytes]) -> tuple[int, int, int]:
    skill_md = published_files(files).get("SKILL.md")
    if skill_md is None:
        raise FrontmatterError("SKILL.md is missing")
    try:
        text = decode_skill_md(skill_md)
    except UnicodeDecodeError as exc:
        raise FrontmatterError("SKILL.md is not valid UTF-8") from exc
    return read_version(parse_frontmatter(text), allow_two_part=True)


def _version_text(version: tuple[int, int, int]) -> str:
    return ".".join(map(str, version))


def check_skill(
    name: str, base: SkillTree | None, head: SkillTree | None, touched: bool = True
) -> SkillReport:
    path = f"{SKILLS_DIR}/{name}"
    if head is None:
        report = SkillReport(path, "removed")
        if base is not None:
            report.errors.append(REMOVED_MESSAGE)
        return report

    change = "added" if base is None else ("changed" if touched else "unchanged")
    report = SkillReport(path, change)
    report.errors += head.errors
    head_result = check_head(name, head.files, strict_version=touched)
    report.errors += head_result.errors
    report.warnings += head_result.warnings
    if head_result.version is not None:
        report.head_version = _version_text(head_result.version)
    if base is None or head_result.version is None:
        return report

    try:
        if base.errors:
            raise FrontmatterError(base.errors[0])
        old_version = base_version(base.files)
    except FrontmatterError as exc:
        report.warnings.append(
            f"the version rules were not checked, because the skill at the base "
            f"commit is not valid: {exc}"
        )
        return report
    report.base_version = _version_text(old_version)
    new_version = head_result.version
    hash_changed = content_hash(published_files(base.files)) != content_hash(
        published_files(head.files)
    )
    if new_version < old_version:
        report.errors.append(
            f"metadata.version went down from {report.base_version} to {report.head_version}"
        )
    elif hash_changed and new_version == old_version:
        report.errors.append(HASH_CHANGED_MESSAGE)
    elif not hash_changed and new_version != old_version:
        report.errors.append(VERSION_ONLY_MESSAGE)
    return report


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, env=env)


def _git_ok(repo_root: Path, *args: str) -> bytes:
    result = _git(repo_root, *args)
    if result.returncode != 0:
        raise SystemExit(
            f"git {' '.join(args)} failed: {result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def _decode_path(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape")


def _diff_base(repo_root: Path, base_ref: str, head_ref: str) -> str:
    result = _git(repo_root, "merge-base", base_ref, head_ref)
    merge_base = result.stdout.decode().strip()
    if result.returncode == 0 and merge_base:
        return merge_base
    print(
        f"warning: no merge base between {base_ref} and {head_ref}; "
        f"diffing against {base_ref} directly",
        file=sys.stderr,
    )
    return base_ref


def changed_paths(repo_root: Path, base: str, head: str) -> list[str]:
    out = _git_ok(repo_root, "diff", "--name-only", "--no-renames", "-z", base, head)
    return [_decode_path(raw) for raw in out.split(b"\0") if raw]


def touched_names(paths: list[str]) -> set[str] | None:
    """Skill folder names with a change, or None when a .gitattributes change touches all of them."""
    if any(path.rsplit("/", 1)[-1] == ".gitattributes" for path in paths):
        return None
    return {
        parts[1]
        for parts in (path.split("/") for path in paths)
        if len(parts) >= 3 and parts[0] == SKILLS_DIR
    }


def _skill_folders(repo_root: Path, rev: str) -> set[str]:
    out = _git_ok(repo_root, "ls-tree", "-z", rev, "--", f"{SKILLS_DIR}/")
    folders = set()
    for raw in out.split(b"\0"):
        meta, _, name = raw.partition(b"\t")
        if meta.split(b" ")[1:2] == [b"tree"]:
            folders.add(_decode_path(name).split("/", 1)[1])
    return folders


def read_skills(repo_root: Path, rev: str) -> tuple[dict[str, SkillTree], list[SkillReport]]:
    """Every skill folder at ``rev`` from one ``git archive``, and reports for unsafe entries directly in skills/."""
    folders = _skill_folders(repo_root, rev)
    trees = {name: SkillTree() for name in folders}
    loose: list[SkillReport] = []
    if not folders:
        return trees, loose
    result = _git(repo_root, "archive", "--format=tar", rev, "--", SKILLS_DIR)
    if result.returncode != 0:
        raise SystemExit(
            f"git archive {rev} {SKILLS_DIR} failed: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    prefix = f"{SKILLS_DIR}/"
    with tarfile.open(fileobj=io.BytesIO(result.stdout), encoding="utf-8") as tar:
        for member in tar:
            entry = member.name
            relative = entry.lstrip("/")
            relative = relative[len(prefix):] if relative.startswith(prefix) else relative
            folder, _, inner = relative.partition("/")
            tree = trees.get(folder) if inner else None
            if entry.startswith("/"):
                error = f"Tarball entry {entry} has an absolute path"
            elif any(segment in ("", ".", "..") for segment in entry.split("/")):
                error = f'Tarball entry {entry} has an empty, "." or ".." path segment'
            elif member.issym() or member.islnk():
                kind = "symlink" if member.issym() else "link"
                error = f"Tarball entry {entry} is a {kind}; links are not allowed"
            else:
                if tree is not None and member.isfile():
                    tree.files[inner] = tar.extractfile(member).read()
                continue
            if tree is not None:
                tree.errors.append(error)
            elif entry != SKILLS_DIR:
                loose.append(SkillReport(entry, "—", errors=[error]))
    return trees, loose


def check_archive(repo_root: Path, rev: str) -> SkillReport:
    """Size of the archive of the whole commit, uncompressed and with gzip."""
    report = SkillReport("(repository archive)", "—")
    raw = 0
    compressed = 0
    compressor = zlib.compressobj(6, zlib.DEFLATED, 31)
    with subprocess.Popen(
        ["git", "archive", "--format=tar", rev], cwd=repo_root, stdout=subprocess.PIPE
    ) as process:
        for chunk in iter(lambda: process.stdout.read(1 << 20), b""):
            raw += len(chunk)
            compressed += len(compressor.compress(chunk))
    compressed += len(compressor.flush())
    if process.returncode != 0:
        raise SystemExit(f"git archive {rev} failed")
    if raw > MAX_ARCHIVE_BYTES:
        report.errors.append(
            f"the repository archive is {raw} bytes; the maximum is {MAX_ARCHIVE_BYTES}"
        )
    if compressed > MAX_COMPRESSED_ARCHIVE_BYTES:
        report.errors.append(
            f"the compressed repository archive is {compressed} bytes; the maximum is "
            f"{MAX_COMPRESSED_ARCHIVE_BYTES}"
        )
    return report


def _escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def _annotate(report: SkillReport) -> None:
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    title = _escape_property(f"Skill publishing: {report.path}")
    for error in report.errors:
        print(f"::error title={title}::{_escape_data(f'{error} — {DOCS_HINT}')}")
    for warning in report.warnings:
        print(f"::warning title={title}::{_escape_data(warning)}")


def _versions(report: SkillReport) -> str:
    return f"{report.base_version or '—'} → {report.head_version or '—'}"


def _write_summary(reports: list[SkillReport]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    shown = [r for r in reports if r.notable]
    quiet = len(reports) - len(shown)
    lines = ["## Skill publishing check", ""]
    if shown:
        lines += ["| Skill | Change | Version | Result |", "| --- | --- | --- | --- |"]
        for r in shown:
            result = "pass" if r.ok else f"**fail** — {len(r.errors)} error(s)"
            if r.warnings:
                result += f", {len(r.warnings)} warning(s)"
            lines.append(f"| `{r.path}` | {r.change} | {_versions(r)} | {result} |")
        lines.append("")
    lines.append(f"{quiet} unchanged skill(s) pass.")
    lines.append("")
    for r in shown:
        if r.errors or r.warnings:
            lines.append(f"### `{r.path}`")
            lines += [f"- error: {_one_line(e)}" for e in r.errors]
            lines += [f"- warning: {_one_line(w)}" for w in r.warnings]
            lines.append("")
    if any(not r.ok for r in reports):
        lines.append(DOCS_HINT)
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def run(repo_root: Path, base_ref: str, head_ref: str) -> list[SkillReport]:
    base = _diff_base(repo_root, base_ref, head_ref)
    touched = touched_names(changed_paths(repo_root, base, head_ref))
    base_trees, _ = read_skills(repo_root, base)
    head_trees, reports = read_skills(repo_root, head_ref)
    for name in sorted(base_trees.keys() | head_trees.keys()):
        reports.append(
            check_skill(
                name,
                base_trees.get(name),
                head_trees.get(name),
                touched=touched is None or name in touched,
            )
        )
    archive = check_archive(repo_root, head_ref)
    if archive.errors:
        reports.append(archive)
    return sorted(reports, key=lambda r: r.path)


def _case_files(files) -> dict[str, bytes]:
    return {
        path: content["text"].encode("utf-8") if "text" in content else base64.b64decode(content["base64"], validate=True)
        for path, content in files.items()
    }


def _check_case(case) -> list[str]:
    case_id = case.get("id") if isinstance(case, dict) else None
    label = f"conformance case {case_id}"
    if (
        not isinstance(case, dict)
        or not isinstance(case_id, str)
        or not set(case) <= CASE_FIELDS
        or not isinstance(case.get("name"), str)
        or not isinstance(case.get("files"), dict)
        or case.get("expect") not in ("pass", "fail")
        or (case["expect"] == "fail" and not isinstance(case.get("error"), str))
    ):
        return [f"{label} is malformed"]
    try:
        files = _case_files(case["files"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return [f"{label} has a malformed file entry"]
    errors = check_head(case["name"], files).errors
    if case["expect"] == "pass":
        return [f"{label} should pass, but fails: {_one_line(errors[0])}"] if errors else []
    expected = case["error"]
    if not errors:
        return [f"{label} should fail with {expected!r}, but passes"]
    if not any(expected in error for error in errors):
        return [f"{label} should fail with {expected!r}, but fails with: {_one_line(errors[0])}"]
    return []


def self_check() -> tuple[list[str], int]:
    """Problems found in the script itself, and the number of conformance cases run."""
    problems = []
    golden = content_hash(GOLDEN_FILES)
    if golden != GOLDEN_HASH:
        problems.append(
            f"the skill content hash of the golden fixture is {golden}, expected {GOLDEN_HASH}"
        )
    relative = "conformance/cases.json"
    try:
        data = CONFORMANCE_FILE.read_bytes()
    except OSError as exc:
        return problems + [f"cannot read {relative}: {exc}"], 0
    digest = hashlib.sha256(data).hexdigest()
    if digest != CONFORMANCE_SHA256:
        problems.append(
            f"{relative} has SHA-256 {digest}, but CONFORMANCE_SHA256 is {CONFORMANCE_SHA256}; "
            "a corpus change must also update CONFORMANCE_SHA256 and conformance/README.md"
        )
    try:
        cases = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        return problems + [f"{relative} is not valid JSON: {exc}"], 0
    if not isinstance(cases, list) or not cases:
        return problems + [f"{relative} must be a non-empty JSON array"], 0
    ids = [str(case.get("id")) if isinstance(case, dict) else "" for case in cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        problems.append(f"{relative} has duplicate ids: {', '.join(duplicates)}")
    if ids != sorted(ids):
        problems.append(f"{relative} is not sorted by id")
    for case in cases:
        problems += _check_case(case)
    return problems, len(cases)


def _report_self_check_failure(problems: list[str]) -> None:
    for problem in problems:
        print(f"::error title=Self-check failed::{_escape_data(problem)}")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        lines = ["## Skill publishing check", "", "The self-check of the script failed, so no skill was checked:", ""]
        lines += [f"- {_one_line(problem)}" for problem in problems]
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None, repo_root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base ref of the pull request (default: origin/main).",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Head ref of the pull request (default: HEAD).",
    )
    parser.add_argument(
        "--self-check-only",
        action="store_true",
        help="Run only the self-check (golden hash, corpus digest, conformance cases).",
    )
    args = parser.parse_args(argv)

    started = time.monotonic()
    problems, case_count = self_check()
    elapsed = time.monotonic() - started
    if problems:
        _report_self_check_failure(problems)
        return 2
    print(
        f"Self-check passed: golden hash, corpus digest, and {case_count} conformance "
        f"cases in {elapsed:.2f} s.",
        file=sys.stderr,
    )
    if args.self_check_only:
        return 0

    reports = run(repo_root or _repo_root(), args.base_ref, args.head_ref)
    shown = [r for r in reports if r.notable]
    for r in shown:
        print(f"{'PASS' if r.ok else 'FAIL'}  {r.path} ({r.change}, {_versions(r)})")
        for error in r.errors:
            print(f"        - {_one_line(error)}")
        for warning in r.warnings:
            print(f"        ! {_one_line(warning)}")
        _annotate(r)
    _write_summary(reports)

    failed = [r for r in reports if not r.ok]
    print(
        f"\n{len(reports)} skill(s) checked: {len(reports) - len(failed)} pass, "
        f"{len(failed)} fail. {len(reports) - len(shown)} unchanged skill(s) that pass "
        "are not listed.",
        file=sys.stderr,
    )
    if failed:
        print(
            "\nWhen one skill on main breaks these rules, no skill is published, so "
            f"merging is blocked. {DOCS_HINT}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
