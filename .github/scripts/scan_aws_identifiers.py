#!/usr/bin/env python3
"""Scan the lines a pull request adds for AWS account IDs and EC2 instance IDs.

The point of the check is to keep unredacted identifiers out of the repository:
an AWS account ID or an EC2 instance ID committed in a skill, an eval result, a
workflow or a document names a real resource in a real account, and once it is
on ``main`` it is in the public history for good.

**An account ID is reported only when something proves it is one.** Twelve
digits on their own are not evidence. Measured against the open pull requests in
this repository, 1008 of 1867 twelve-digit runs on their added lines — 54% —
name no account, in four shapes: a ``YYYYMMDDHHMM`` datestamp used as a
resource-name suffix (916 hits), the fractional digits of a decimal (57 hits),
the integer part of a decimal (7 hits), and a zero-padded counter (28 hits).
Synthetic examples of all four, and of the twelve-digit run inside a longer
hexadecimal resource id, are in ``REPORTING_CASES`` at the foot of this file.
So the scan works in two passes.

**Pass one gathers evidence and reports nothing.** Three sources put a value in
a position that only an account ID occupies:

1. The account field of an ARN. ``arn:partition:service:region:account-id:…``
   — when the fifth colon-separated field is exactly twelve digits, those digits
   are an account ID.
2. An object key in the tool result of a ``tool_summary`` block, in a file named
   ``journal_records.json``. The DevOps Agent journal records a per-account AWS
   API result as a map keyed by account ID, as in
   ``{"123456789012": {"DBInstances": []}}``.
3. The value of an ``aws_account_id`` field, in a file named
   ``journal_records.json``. That field name is part of the DevOps Agent journal
   schema, and it appears both in a recorded tool input and in agent prose.

Only those three. Other spellings an AWS API response or a human might use —
``AccountId``, ``accountId``, ``Account`` — are deliberately not read, because
the two journal sources above are schema-defined fields whose meaning is fixed,
while a loose field-name match would reintroduce guesswork.

Pass one reads **every file the pull request changes, whole**, not just the added
lines. Evidence costs nothing to collect, and the wider read means an account ID
written bare on an added line is still caught when the ARN that proves it sits
in a part of the file the pull request never touched.

**Pass two reports, and only on the lines the pull request adds:**

* Any ARN whose account field holds a twelve-digit value that is not
  allowlisted. The finding is the **whole ARN**, not the account segment inside
  it. Flagging only the segment would let an author blank that one field and
  leave the region, the service and the resource name in place — and a surviving
  copy of the account ID elsewhere in the file would be enough to rebuild the
  full ARN. Making the ARN the finding makes the remedy "remove this ARN".
* Any occurrence of an account ID that pass one proved, anywhere on an added
  line, in any file type. This is what catches the same account written bare in
  prose or in a field this scan does not read.
* An EC2 instance ID: ``i-`` followed by either eight hexadecimal characters
  (the old form) or seventeen (the current form). An instance ID is
  self-evidencing — its prefix and length are the proof — so it needs no pass
  one.

**An ARN with no account field is not reported.** ``arn:aws:s3:::my-bucket`` and
``arn:aws:iam::aws:policy/ReadOnlyAccess`` name no account, and there is no
reliable way to tell a real bucket from an example one: anybody may own
``arn:aws:s3:::my-internal-bucket`` or ``arn:aws:s3:::example-bucket``, so
reporting them would be noise. Of 121 account-less ARNs on the open pull
requests' added lines, none named a private resource — 97 were templates or
explicit examples, 21 were placeholders or AWS-published service quota codes, 3
were truncated. Redacting a real S3 bucket ARN is the author's job, and catching
one is a human reviewer's.

**The known gap**, stated plainly so nobody mistakes a pass for a guarantee: an
account ID that appears only as prose in a file that is not a journal — "the
cluster in account 123456789012", with no ARN anywhere in that file — is proved
by none of the three sources and is not reported.

**Scope: only the lines the pull request adds are reported on.** The diff is read
with ``git diff --find-renames --unified=0 <base-ref>...<head-ref>``; only the
``+`` lines of that diff are scanned for findings, and removed lines, context
lines and the ``+++``/``---`` file headers are all ignored. Reporting on whole
files, or on the whole tree, was rejected deliberately: ``main`` already carries
real identifiers — committed eval results, example ARNs in skill documentation,
a handful of values in MCP comments — so a whole-file report would fail pull
requests for content their authors never wrote, and the only way to go green
would be to clean up someone else's lines. Cleaning those up is a separate
change; this check stops new ones arriving.

``--find-renames`` is part of that scope and not a nicety. Without it a pure
file rename is reported as a deletion plus an addition of every line, so moving
a file that already contains identifiers would fail the check for a change that
added nothing. With it, a pure rename produces no added lines at all.

**Redaction suffixes.** The skill evaluation tool redacts identifiers by
replacing each distinct original with a placeholder plus an index, as in
``012345678901_2`` and ``i-1234567890abcdef0_2``, where the trailing number
tells two different originals apart. A matched identifier therefore has an
optional trailing ``_<digits>`` stripped from it before it is compared against
the allowlist, so the bare placeholder and every indexed form of it are treated
alike. The finding reports the token as written; only the comparison is
normalized.

**Three ways a match is suppressed:**

1. The file being scanned *is* the allowlist. Added lines in
   ``.github/aws-identifier-allowlist.json`` are skipped, so adding an entry to
   the allowlist does not trip the scanner on that very entry.
2. An entry in the allowlist file, which must carry a reason. An allowlisted
   account ID is dropped from the proven set, which suppresses both the bare
   occurrences of it and any ARN that names it.
3. An ``aws-id-ok: <reason>`` marker on the line. Honored in file types that
   have a comment syntax — ``.md``, ``.yaml``, ``.yml``, ``.py``, ``.sh``,
   ``.ts``, ``.js``, ``.html``, ``.htm``, ``.xml``. JSON has no comment syntax,
   which is why the allowlist is the route for JSON content.

The allowlist-path skip comes first, and the marker is checked last, after the
patterns have run: a line naming the marker but holding no identifier suppresses
nothing, so it is left alone rather than treated as an opt-out.

Exit codes: ``0`` when nothing was found, including a pull request that adds no
lines at all; ``1`` when there are findings; ``2`` when the scan could not be
trusted — a malformed allowlist, an unreadable diff file, or a failing ``git``
command. The gate workflow fails the job on any non-zero code; the split exists
so a contributor can tell a leaked identifier from a broken allowlist.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# An AWS account ID as a complete value: exactly twelve digits, with the skill
# evaluation tool's optional ``_<index>`` redaction suffix. Used with
# ``fullmatch`` on a value that some structure has already singled out — an ARN
# field, a journal object key, an ``aws_account_id`` value, an allowlist entry —
# never to go hunting for twelve digits in free text.
ACCOUNT_VALUE_RE = re.compile(r"([0-9]{12})(?:_([0-9]+))?")

# An ARN, parsed by position. The AWS reference
# (https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html) gives
# three forms:
#
#     arn:partition:service:region:account-id:resource-id
#     arn:partition:service:region:account-id:resource-type/resource-id
#     arn:partition:service:region:account-id:resource-type:resource-id
#
# They differ only in what *follows* the account, so the parse does not branch:
# the account is always the fifth colon-separated field, and everything after it
# is the resource.
#
# The account field is matched loosely and judged in code rather than being
# pinned to twelve digits here, so that an ARN with an empty account
# (``arn:aws:s3:::my-bucket``), the literal ``aws``
# (``arn:aws:iam::aws:policy/ReadOnlyAccess``) or a redaction suffix
# (``012345678901_1``) all still parse — and are then handled on their merits.
# Every field before the resource also accepts a CloudFormation template
# expression such as ``${AWS::Region}``, which is why ARN_TEMPLATE_FIELD below
# swallows the braces whole: ``${AWS::Region}`` carries a ``::`` of its own, so
# without it the fields cannot be lined up and the match fails outright. The
# field that matters there is not the templated one but the account beside it --
# ``arn:aws:lambda:${AWS::Region}:<a literal account>:layer:X`` is how a SAM
# template names a published layer, and a failed parse means that literal
# account is neither proved nor reported. A template expression in the account
# field itself stays silent, but silent because the field is not twelve digits,
# which is a judgement ``arn_accounts`` makes, rather than because the ARN
# failed to parse.
#
# Only the ``${...}`` form is covered, because that is the one this repository
# uses. An ARN written with another placeholder syntax in a field before the
# resource -- ``{Region}``, ``<region>``, ``%REGION%`` -- still fails to parse,
# and an account standing beside one of those would go unreported. See the
# documented gaps in CONTRIBUTING.md.
#
# The partition is ``aws`` plus any number of lowercase suffixes, which covers
# the three in practice: ``aws``, ``aws-cn``, ``aws-us-gov``. The region may be
# empty. The resource may be empty too, so a truncated ARN that stops right
# after the account still yields its account.
#
# Every field before the resource also accepts ``*``, because an IAM policy
# scopes a resource by wildcarding whichever fields it does not care about:
# ``arn:aws:logs:*:123456789012:log-group:/aws/lambda/x`` is the ordinary way to
# name a log group in every region, and this repository ships seven policy JSON
# files written that way. Without ``*`` in the region class the regex demands a
# ``:`` where the ``*`` sits, the whole match fails, and the account field is
# never read at all — so a policy file naming a real account would prove nothing
# and be reported as nothing. A wildcard in the partition or the account field
# should also be silent, but silent because the account field is not twelve
# digits, which is a judgement ``arn_accounts`` makes, rather than because the
# ARN failed to parse.
#
# A ``${...}`` template expression, matched before the plainer classes so the
# braces are consumed as one unit rather than left to a class that would stop at
# the first ``:`` inside them.
ARN_TEMPLATE_FIELD = r"\$\{[^}]*\}"
ARN_RE = re.compile(
    r"arn:"
    r"(?P<partition>" + ARN_TEMPLATE_FIELD + r"|\*|aws(?:-[a-z0-9*]+)*):"
    r"(?P<service>" + ARN_TEMPLATE_FIELD + r"|[a-z0-9*][a-z0-9*-]*):"
    r"(?P<region>" + ARN_TEMPLATE_FIELD + r"|[a-z0-9*-]*):"
    r"(?P<account>" + ARN_TEMPLATE_FIELD + r"|[0-9A-Za-z_*-]*):"
    # The resource ends where the surrounding text begins. Whitespace, a quote,
    # a backtick, a backslash (an ARN inside an escaped JSON string ends at the
    # escape), a comma and the closing brackets are all excluded, because each
    # of them delimits an ARN far more often than it occurs inside one.
    r"(?P<resource>[^\s\"'`\\,<>|)\]}]*)"
)

# Trailing characters stripped from a reported ARN. A sentence ending in an ARN
# leaves the full stop inside the match, and a truncated ARN leaves a dangling
# colon. Only the reported string is trimmed; the account was already read from
# its own field, so the trim cannot change what is detected.
ARN_TRAILING_PUNCTUATION = ".;:"

# ``i-`` plus either of the two legal lengths, seventeen hexadecimal characters
# (current) or eight (the old form), with the seventeen-character alternative
# first so the longer match wins.
#
# The left guard is the non-obvious part: without it, ``ami-0abcdef1234567890``
# would match from its ``i-`` and every AMI id in the repository would be
# reported as an instance id. The right guard rejects an eighteenth hexadecimal
# character, so a longer token is not mistaken for a seventeen-character id.
INSTANCE_RE = re.compile(
    r"(?<![0-9A-Za-z])(i-(?:[0-9a-f]{17}|[0-9a-f]{8}))(?:_([0-9]+))?(?![0-9A-Za-z])",
    re.IGNORECASE,
)

# The only file name whose contents are read for the two journal sources of
# evidence. DevOps Agent writes its journal to this name, and the two field
# positions below are part of that journal's schema — so reading them out of
# some other JSON file would be reading a field that means something else.
JOURNAL_FILE_NAME = "journal_records.json"

# The journal nests JSON inside JSON: a record's ``content`` is a string holding
# more JSON, which can itself hold a string holding more JSON. The walk parses
# each such string and recurses, and this caps how far down it goes, so a
# pathological or self-referential file cannot spin the scan.
JOURNAL_MAX_DEPTH = 16

# The journal block whose tool result is keyed by account ID.
TOOL_SUMMARY_BLOCK = "tool_summary"

# The journal field whose value is an account ID.
JOURNAL_ACCOUNT_FIELD = "aws_account_id"

# A second reading of the ``aws_account_id`` field, straight off the raw text.
# It runs on every journal, alongside the walk rather than instead of it, and it
# exists to cover the journals the walk cannot reach: a truncated journal that
# will not parse, or a record whose escaping is deeper than the walk unwinds.
# Reading the same field twice costs one pass over the text and can only add the
# value the walk would have added anyway.
#
# The separator class covers every form the field takes
# in a real journal — ``"aws_account_id": "123456789012"``, the same escaped as
# ``\"aws_account_id\": \"123456789012\"``, and agent prose writing
# ``aws_account_id `123456789012` `` — and is bounded so the match cannot run
# from the field name across unrelated text into some other number. The closing
# guard rejects a thirteenth digit.
JOURNAL_ACCOUNT_FIELD_RE = re.compile(
    JOURNAL_ACCOUNT_FIELD + r"""[\s:=,"'`()\\]{0,16}([0-9]{12})(?:_([0-9]+))?(?![0-9A-Za-z])"""
)

ACCOUNT_KIND = "AWS account ID"
ARN_KIND = "ARN naming an AWS account"
INSTANCE_KIND = "EC2 instance ID"

# Per-line opt-out. A line carrying this marker is skipped entirely.
MARKER = "aws-id-ok"
MARKER_WITH_REASON_RE = re.compile(r"aws-id-ok\s*:\s*\S")

# File types where the marker is honored, because a line in them can carry a
# comment. The check is a substring test on the line rather than a parse of the
# language's comment syntax — an approximation, and a generous one: a marker
# inside a string literal in a .py file suppresses that line too. The marker is
# a deliberate opt-out written by the author of the line, so being generous
# about where it sits costs little, while parsing nine languages to be strict
# about it would cost a lot.
COMMENT_BEARING_SUFFIXES = {
    ".md",
    ".yaml",
    ".yml",
    ".py",
    ".sh",
    ".ts",
    ".js",
    ".html",
    ".htm",
    ".xml",
}

# Repository-relative path of the allowlist the gate workflow uses.
DEFAULT_ALLOWLIST = ".github/aws-identifier-allowlist.json"

# Findings are printed and tabulated up to this many; the rest are reported as a
# count. A pull request that adds hundreds of identifiers needs the first screen
# of them and a total, not a wall of annotations.
MAX_PRINTED_FINDINGS = 50

REMEDIATION = (
    "To resolve a finding: redact the value — for an ARN, remove the whole ARN, "
    "since blanking its account field leaves the rest of it in place — or add "
    f"the account ID or instance ID to `{DEFAULT_ALLOWLIST}` with a reason "
    "explaining why it is safe to publish, or put an "
    f"`{MARKER}: <reason>` comment on the line itself. The allowlist is the "
    "route for JSON files, which have no comment syntax. See the "
    '"Scanning for AWS Identifiers" section of CONTRIBUTING.md.'
)


@dataclass
class Finding:
    path: str
    line: int
    kind: str
    # The token exactly as it appears on the line, redaction suffix included, so
    # the message matches what the author will search for in the file. For an
    # ARN finding this is the whole ARN.
    value: str


def _repo_root() -> Path:
    """Resolve the repository root from this script's location (.github/scripts/)."""
    return Path(__file__).resolve().parents[2]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        errors="replace",
    )


def _warn(message: str) -> None:
    """Report a non-fatal problem, as an annotation under Actions."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning::{message.replace(chr(10), ' ')}")
    else:
        print(f"warning: {message}", file=sys.stderr)


def _error(message: str) -> None:
    """Report a fatal problem, as an annotation under Actions."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error::{message.replace(chr(10), ' ')}")
    else:
        print(f"error: {message}", file=sys.stderr)


def read_diff(repo_root: Path, base_ref: str, head_ref: str) -> str | None:
    """Return the unified diff of what ``head_ref`` adds, or None on failure.

    The flags each earn their place:

    * ``<base_ref>...<head_ref>`` — a three-dot diff, against the merge base, so
      commits that landed on the base branch after the pull request branched are
      not attributed to the pull request.
    * ``--find-renames`` — without it a pure rename is reported as every line
      being added, which would flag identifiers the pull request only moved.
    * ``--unified=0`` — only added lines are reported on, so context lines are
      output nobody reads.
    * ``core.quotePath=false`` — a non-ASCII path is printed as itself in the
      ``+++`` header rather than octal-escaped, which keeps the reported file
      path usable.

    A failing three-dot diff is retried with two dots, which covers the case of
    a shallow clone or an unrelated history where no merge base exists. When
    both fail the caller exits with the configuration failure code: a scan that
    cannot read the diff has to fail loudly rather than report "nothing found".
    """
    flags = (
        "-c",
        "core.quotePath=false",
        "diff",
        "--find-renames",
        "--unified=0",
        "--no-color",
    )

    result = _git(repo_root, *flags, f"{base_ref}...{head_ref}")
    if result.returncode == 0:
        return result.stdout

    _warn(
        f"git diff {base_ref}...{head_ref} failed "
        f"({result.stderr.strip()}); retrying without the merge base"
    )
    result = _git(repo_root, *flags, base_ref, head_ref)
    if result.returncode == 0:
        return result.stdout

    _error(
        f"git diff {base_ref} {head_ref} failed: {result.stderr.strip()}. "
        "The scan cannot run without a diff."
    )
    return None


def read_diff_file(path: str) -> str | None:
    """Read a saved diff from ``path``, or from stdin when ``path`` is ``-``.

    This is the local-testing entry point: with a saved diff the scanner runs no
    ``git`` command at all, which makes it easy to exercise against a fixture.
    """
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _error(f"cannot read diff file `{path}`: {exc}")
        return None


def added_lines(diff_text: str) -> list[tuple[str, int, str]]:
    """Parse a unified diff into (path, line number in the new file, line text).

    Only added lines are returned, and the leading ``+`` is stripped from the
    text. The ``+++``/``---`` headers are skipped rather than scanned, so a file
    path that happens to contain a twelve-digit run is never reported as
    content.

    The headers are recognised only outside a hunk. Unified diff is ambiguous
    here: an added line whose own text starts with ``++ `` appears in the diff
    as ``+++ ``, exactly like a file header. Tracking whether the parser is
    inside a hunk resolves it, since a header never appears inside one.

    The line counter comes from the hunk header and advances on added and
    context lines but not on removed ones, which is how a line number in the new
    file is reached. Context lines are counted even though ``--unified=0`` emits
    none, so that a fixture diff generated with default context parses correctly
    too.
    """
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    entries: list[tuple[str, int, str]] = []
    path: str | None = None
    line_number = 0
    in_hunk = False

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            path, in_hunk = None, False
            continue
        if not in_hunk and raw.startswith("+++ "):
            target = raw[4:].strip()
            # /dev/null is a deleted file: its hunks hold only removed lines.
            path = None if target == "/dev/null" else _strip_diff_prefix(target)
            continue
        if not in_hunk and raw.startswith("--- "):
            continue
        match = hunk_re.match(raw)
        if match:
            line_number = int(match.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            # index / mode / similarity / rename / binary header lines.
            continue
        if raw.startswith("+"):
            if path is not None:
                entries.append((path, line_number, raw[1:]))
            line_number += 1
        elif raw.startswith("-"):
            pass  # removed line: not part of what the pull request adds
        elif raw.startswith("\\"):
            pass  # "\ No newline at end of file"
        else:
            line_number += 1  # context line

    return entries


def changed_paths(diff_text: str) -> list[str]:
    """Paths of every file the diff touches, in the order the diff names them.

    This is wider than the set of paths in ``added_lines``: a file the pull
    request only deletes lines from still names an ARN in the lines it keeps,
    and that ARN still proves an account ID an added line elsewhere mentions
    bare. A deleted file is left out, since there is nothing to read at the head
    ref.

    The ``+++`` header is recognised only outside a hunk, for the same reason
    ``added_lines`` tracks that state: an added line whose own text starts with
    ``++ `` appears in the diff looking exactly like a file header.
    """
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")

    paths: list[str] = []
    in_hunk = False
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            in_hunk = False
            continue
        if not in_hunk and raw.startswith("+++ "):
            target = raw[4:].strip()
            if target != "/dev/null":
                path = _strip_diff_prefix(target)
                if path not in paths:
                    paths.append(path)
            continue
        if hunk_re.match(raw):
            in_hunk = True
    return paths


def _strip_diff_prefix(target: str) -> str:
    """Drop the ``b/`` that ``git diff`` puts in front of the new file's path."""
    return target[2:] if target.startswith(("a/", "b/")) else target


def load_allowlist(path: Path) -> tuple[set[str], set[str], list[str]]:
    """Read the allowlist, returning (account IDs, instance IDs, problems).

    The shape is two required objects, each mapping an identifier to the reason
    it is safe to publish::

        {
          "account_ids":  {"123456789012": "AWS documentation example"},
          "instance_ids": {"i-0123456789abcdef0": "AWS documentation example"}
        }

    The reason is mandatory. An allowlist entry waives a check on published
    content, and the reason is what a reviewer judges the waiver on.

    **The parser fails closed**: an unreadable file, invalid JSON, a top level
    that is not an object, a missing key, a value that is not an object, a key
    that does not look like the identifier it claims to be, or a reason that is
    missing or blank — each is reported as a problem, and when there is any
    problem the function grants no allowance at all.

    That is the opposite of how ``parse_label_names`` in validate_skill_evals.py
    treats a mangled value, and deliberately so. The label that script reads can
    only make its check stricter, so treating a mangled one as absent is safe.
    An allowlist only ever makes this check *weaker*. Degrading a broken
    allowlist to "allow nothing" would be noisy but safe, and degrading it to
    "allow everything" would silently waive a real leak — so rather than guess,
    a broken allowlist is itself an error, reported with the reason and exiting
    with the configuration failure code.
    """
    rel = path.name
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return set(), set(), [f"cannot read allowlist `{path}`: {exc}"]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return set(), set(), [f"`{rel}` is not valid JSON ({exc})"]

    if not isinstance(raw, dict):
        return (
            set(),
            set(),
            [f"`{rel}` must be a JSON object with `account_ids` and `instance_ids`"],
        )

    problems: list[str] = []
    collected: dict[str, set[str]] = {"account_ids": set(), "instance_ids": set()}
    patterns = {"account_ids": ACCOUNT_VALUE_RE, "instance_ids": INSTANCE_RE}

    for key, pattern in patterns.items():
        if key not in raw:
            problems.append(f"`{rel}` is missing the `{key}` object")
            continue
        body = raw[key]
        if not isinstance(body, dict):
            problems.append(
                f"`{rel}` key `{key}` must be an object mapping identifier to reason"
            )
            continue
        for identifier, reason in body.items():
            if not isinstance(identifier, str) or not pattern.fullmatch(identifier):
                problems.append(
                    f"`{rel}` entry `{identifier}` under `{key}` is not a valid "
                    "identifier of that type"
                )
                continue
            if not isinstance(reason, str) or not reason.strip():
                problems.append(
                    f"`{rel}` entry `{identifier}` needs a non-empty reason "
                    "explaining why the value is safe to publish"
                )
                continue
            collected[key].add(_normalize(identifier))

    if problems:
        # Fail closed: no allowance at all while the file is broken.
        return set(), set(), problems

    return collected["account_ids"], collected["instance_ids"], []


def _normalize(value: str) -> str:
    """Lowercase an identifier and drop any ``_<digits>`` redaction suffix.

    Comparisons against the allowlist and against the proven account IDs use
    this form, so ``i-1234567890abcdef0``, ``I-1234567890ABCDEF0`` and
    ``i-1234567890abcdef0_2`` all resolve to the one allowlist entry, and
    ``123456789012_3`` on a line matches ``123456789012`` proven in an ARN.
    """
    return re.sub(r"_[0-9]+$", "", value).lower()


def changed_file_documents(
    repo_root: Path,
    head_ref: str | None,
    paths: list[str],
    entries: list[tuple[str, int, str]],
) -> list[tuple[str, str]]:
    """Return (path, whole file text at ``head_ref``) for every changed file.

    This is the input to the evidence pass, and it is wider than what the
    reporting pass reads: every file the diff touches, whole, rather than the
    added lines. An ARN sitting in a part of the file the pull request never
    touched still proves the account ID that an added line mentions bare, and
    reading it costs one ``git show``.

    ``git show`` is read-only, as is every other ``git`` call this scanner makes.
    Reading from the working tree instead was rejected because ``head_ref`` is
    not always what is checked out — a local run against ``pr/112`` never checks
    that branch out.

    When ``head_ref`` is None the caller is scanning a saved diff with
    ``--diff-file`` and there is no ref to read from, so each file's added lines,
    joined back together, stand in for its contents. The same stand-in covers a
    file ``git show`` cannot produce as text, a binary asset most likely. Both
    cases narrow the evidence pass to the added lines, which is the scope the
    reporting pass uses anyway.
    """
    added_by_path: dict[str, list[str]] = {}
    for path, _line_number, text in entries:
        added_by_path.setdefault(path, []).append(text)

    documents: list[tuple[str, str]] = []
    for path in paths:
        whole = _head_file_text(repo_root, head_ref, path) if head_ref else None
        if whole is None:
            whole = "\n".join(added_by_path.get(path, []))
        if whole:
            documents.append((path, whole))
    return documents


def _head_file_text(repo_root: Path, head_ref: str, path: str) -> str | None:
    """Return the text of ``path`` at ``head_ref``, or None when git cannot.

    None covers a path that is absent at that ref — a file the pull request
    deletes still has a diff entry — and anything git declines to print.
    Undecodable bytes are replaced rather than raising, so a binary asset
    yields harmless text instead of killing the scan.
    """
    result = _git(repo_root, "show", f"{head_ref}:{path}")
    return result.stdout if result.returncode == 0 else None


def arn_accounts(text: str) -> set[str]:
    """Account IDs read out of the account field of every ARN in ``text``.

    The field is evidence because of where it sits, not because of how it looks:
    an ARN's fifth colon-separated field holds an account ID or nothing at all.
    An empty field (``arn:aws:s3:::my-bucket``), the literal ``aws``
    (``arn:aws:iam::aws:policy/ReadOnlyAccess``) and anything else that is not
    twelve digits yield nothing.
    """
    found: set[str] = set()
    for match in ARN_RE.finditer(text):
        account = match.group("account")
        if ACCOUNT_VALUE_RE.fullmatch(account):
            found.add(_normalize(account))
    return found


def journal_accounts(text: str) -> set[str]:
    """Account IDs read out of a DevOps Agent journal, from its two fields.

    The journal nests JSON inside JSON — a record's ``content`` is a string
    holding more JSON, sometimes several levels down, and the same block can
    appear both as parsed structure and as an escaped string — so the two fields
    are read by walking the parsed tree and parsing every string that starts a
    JSON object or array along the way. A regex over the raw escaped text cannot
    be the primary mechanism, because the escaping varies in depth: ``\\"``,
    ``\\\\"`` and deeper all occur in real journals, and a pattern pinned to one
    depth silently misses the others.

    ``JOURNAL_ACCOUNT_FIELD_RE`` then reads the same ``aws_account_id`` field a
    second time, straight off the raw text. It runs on every journal, not only
    on one the walk failed to parse, because deciding in advance whether the
    walk reached every record would cost more than reading the text again. What
    it is there for is the journal the walk cannot reach: one truncated
    mid-record, or one whose escaping is deeper than the walk unwinds. It can
    only add the value the walk would have added anyway.
    """
    found: set[str] = set()

    try:
        tree = json.loads(text)
    except (ValueError, RecursionError):
        tree = None
    if tree is not None:
        _walk_journal(tree, False, 0, found)

    for match in JOURNAL_ACCOUNT_FIELD_RE.finditer(text):
        found.add(match.group(1))

    return found


def _walk_journal(
    node: object, in_tool_summary: bool, depth: int, found: set[str]
) -> None:
    """Collect account IDs from a journal subtree into ``found``.

    Two positions count, and both are part of the DevOps Agent journal schema:

    * An object key of exactly twelve digits anywhere below a block whose
      ``block_type`` is ``tool_summary``. The journal stores a per-account AWS
      API result as a map keyed by account ID, so the key *is* the account —
      ``{"123456789012": {"DBInstances": []}}`` under
      ``tool_summary > tool_result > text``.
    * The value of an ``aws_account_id`` field, anywhere in the tree. It appears
      in a recorded tool input and in agent prose alike.

    ``in_tool_summary`` is carried down rather than recomputed, because the key
    sits several levels below the block that gives it its meaning.
    """
    if depth > JOURNAL_MAX_DEPTH:
        return

    if isinstance(node, str):
        # A string that starts an object or an array is nested JSON; anything
        # else is a leaf and json.loads would only raise on it.
        stripped = node.lstrip()
        if stripped[:1] in ("{", "["):
            try:
                nested = json.loads(stripped)
            except (ValueError, RecursionError):
                return
            _walk_journal(nested, in_tool_summary, depth + 1, found)
        return

    if isinstance(node, list):
        for item in node:
            _walk_journal(item, in_tool_summary, depth + 1, found)
        return

    if isinstance(node, dict):
        inside = in_tool_summary or node.get("block_type") == TOOL_SUMMARY_BLOCK
        for key, value in node.items():
            if inside and isinstance(key, str) and ACCOUNT_VALUE_RE.fullmatch(key):
                found.add(_normalize(key))
            if key == JOURNAL_ACCOUNT_FIELD and isinstance(value, (str, int)):
                candidate = str(value)
                if ACCOUNT_VALUE_RE.fullmatch(candidate):
                    found.add(_normalize(candidate))
            _walk_journal(value, inside, depth + 1, found)


def extract_accounts(documents: list[tuple[str, str]]) -> set[str]:
    """Account IDs proved by the three sources, across every changed file.

    ARNs are read in every file, whatever its type. The two journal fields are
    read only in a file named ``journal_records.json``, because they are fields
    of the DevOps Agent journal schema and the same names in some other file
    would mean something else.
    """
    proven: set[str] = set()
    for path, text in documents:
        proven |= arn_accounts(text)
        if Path(path).name == JOURNAL_FILE_NAME:
            proven |= journal_accounts(text)
    return proven


def accounts_to_flag(
    documents: list[tuple[str, str]], allowed_accounts: set[str]
) -> set[str]:
    """The proven account IDs, less the ones the allowlist covers."""
    return extract_accounts(documents) - allowed_accounts


def account_occurrence_re(accounts: set[str]) -> re.Pattern[str] | None:
    """One pattern matching any of ``accounts`` as a whole token, or None.

    The two boundary lookarounds are cheap insurance rather than the thing that
    keeps false positives out — that job now belongs to the evidence pass, which
    only ever hands this function a value some structure proved to be an account
    ID. They cover the remaining coincidence: a proven account whose digits also
    sit inside a longer token, such as a hexadecimal resource id, where the
    longer token is the real reference and the account is not being named at
    all. The optional ``_<digits>`` group consumes the skill evaluation tool's
    redaction suffix, which matters because ``_`` is a word character and a
    ``\\b``-anchored pattern would not match the suffixed form at all.

    None when nothing was proven, which lets the caller skip the search.
    """
    if not accounts:
        return None
    alternatives = "|".join(re.escape(account) for account in sorted(accounts))
    return re.compile(
        rf"(?<![0-9A-Za-z])({alternatives})(?:_([0-9]+))?(?![0-9A-Za-z])"
    )


def _excluded_paths(repo_root: Path, allowlist: Path) -> set[str]:
    """Repository-relative paths whose added lines are never reported on.

    The allowlist file itself, so that adding ``123456789012`` to it does not
    make the scanner report that very entry. Both the file in use and the
    default are listed, so a local run against a temporary allowlist still
    skips the committed one, which is the file a pull request would be editing.
    """
    excluded = {DEFAULT_ALLOWLIST}
    try:
        excluded.add(allowlist.resolve().relative_to(repo_root).as_posix())
    except ValueError:
        pass  # a --allowlist outside the repository has no diff path to skip
    return excluded


def scan_added_lines(
    entries: list[tuple[str, int, str]],
    proven_accounts: set[str],
    allowed_accounts: set[str],
    allowed_instances: set[str],
    excluded: set[str],
) -> tuple[list[Finding], list[str]]:
    """Report identifiers on added lines, returning (findings, warnings).

    Three things are reported, in this order:

    1. An ARN whose account field holds a twelve-digit value the allowlist does
       not cover, reported as the whole ARN. ``proven_accounts`` is not
       consulted for this: the ARN on the line is its own evidence.
    2. An occurrence of any account ID in ``proven_accounts``, reported as the
       token on the line. The account field of an ARN already reported above is
       skipped, so one ARN produces one finding rather than two overlapping
       ones. Only that field is skipped: a *different* account ID appearing in
       the ARN's resource name is still reported in its own right.
    3. An EC2 instance ID, which needs no evidence — its prefix and length are
       the proof.

    The marker is applied *after* the patterns rather than before. A line that
    mentions ``aws-id-ok`` but carries no identifier is suppressing nothing, so
    it neither counts as an opt-out nor earns the missing-reason warning —
    without which every line of documentation or source that names the marker,
    this file's own ``MARKER`` constant included, would be warned about.
    """
    findings: list[Finding] = []
    warnings: list[str] = []
    occurrence_re = account_occurrence_re(proven_accounts)

    for path, line_number, text in entries:
        if path in excluded:
            continue

        candidates: list[Finding] = []
        # Character ranges of the account fields of the ARNs already reported on
        # this line, so the occurrence search below does not report the same
        # digits a second time.
        reported_account_spans: list[tuple[int, int]] = []

        for match in ARN_RE.finditer(text):
            account = match.group("account")
            if not ACCOUNT_VALUE_RE.fullmatch(account):
                continue  # no account field, the literal `aws`, or a template
            if _normalize(account) in allowed_accounts:
                continue
            arn = match.group(0).rstrip(ARN_TRAILING_PUNCTUATION)
            reported_account_spans.append(match.span("account"))
            candidates.append(Finding(path, line_number, ARN_KIND, arn))

        if occurrence_re is not None:
            for match in occurrence_re.finditer(text):
                if any(
                    start <= match.start() < end
                    for start, end in reported_account_spans
                ):
                    continue
                candidates.append(
                    Finding(path, line_number, ACCOUNT_KIND, match.group(0))
                )

        for match in INSTANCE_RE.finditer(text):
            if _normalize(match.group(1)) in allowed_instances:
                continue
            candidates.append(
                Finding(path, line_number, INSTANCE_KIND, match.group(0))
            )

        if not candidates:
            continue

        suffix = Path(path).suffix.lower()
        if suffix in COMMENT_BEARING_SUFFIXES and MARKER in text:
            if not MARKER_WITH_REASON_RE.search(text):
                warnings.append(
                    f"{path}:{line_number} suppresses the AWS identifier scan with "
                    f"a bare `{MARKER}` marker; write `{MARKER}: <reason>` so a "
                    "reviewer can see why the value is safe to publish"
                )
            continue

        findings += candidates

    return findings, warnings


def _annotate(findings: list[Finding], warnings: list[str]) -> None:
    """Emit GitHub Actions annotations, one per finding.

    Each finding is anchored with ``file=`` and ``line=`` so it appears inline on
    the pull request's diff, next to the line that added the identifier.
    Annotations are single-line, so any embedded newline is flattened.
    """
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    for finding in findings[:MAX_PRINTED_FINDINGS]:
        message = (
            f"{finding.kind} `{finding.value}` was added on this line. {REMEDIATION}"
        )
        print(
            f"::error file={finding.path},line={finding.line},"
            f"title=AWS identifier::{message.replace(chr(10), ' ')}"
        )
    for warning in warnings:
        print(f"::warning title=AWS identifier::{warning.replace(chr(10), ' ')}")


def _write_summary(
    findings: list[Finding], warnings: list[str], problems: list[str]
) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## AWS identifier scan", ""]

    if problems:
        lines.append("### Allowlist problems")
        lines.append("")
        lines += [f"- {problem}" for problem in problems]
        lines += [
            "",
            f"No allowance was granted while `{DEFAULT_ALLOWLIST}` is broken, so "
            "findings below may include values the allowlist is meant to cover. "
            "Fix the file and re-run.",
            "",
        ]

    if not findings:
        lines.append(
            "No AWS account IDs or EC2 instance IDs were added by this pull request."
        )
    else:
        lines.append(f"{len(findings)} finding(s) on lines this pull request adds:")
        lines.append("")
        lines.append("| File | Line | Kind | Value |")
        lines.append("| --- | --- | --- | --- |")
        for finding in findings[:MAX_PRINTED_FINDINGS]:
            lines.append(
                f"| `{finding.path}` | {finding.line} | {finding.kind} "
                f"| `{finding.value}` |"
            )
        remainder = len(findings) - MAX_PRINTED_FINDINGS
        if remainder > 0:
            lines.append(f"| … and {remainder} more | | | |")
        lines += ["", REMEDIATION]

    if warnings:
        lines += ["", "### Warnings", ""]
        lines += [f"- {warning}" for warning in warnings]

    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Self-check cases
#
# Every case below uses a documentation placeholder — `123456789012`,
# `111122223333`, `012345678901`, `i-1234567890abcdef0` — and never an invented
# real-looking value. This file is scanned by its own check, and a twelve-digit
# value in an ARN here would be a finding against the pull request that edits the
# scanner. The reporting cases get around the allowlist by running with an empty
# allowlist, which is what lets a placeholder stand in for a real account: with
# nothing allowed, `123456789012` is reported exactly as a real account ID would
# be. The suppression cases run with the allowlist in use, and assert silence.
# ---------------------------------------------------------------------------

# (label, file path, whole file text, account IDs the evidence pass should prove)
#
# These pin the evidence pass, whose failures are silent: an account ID that
# stops being proved stops being reported, and a passing check is the only
# symptom.
EXTRACTION_CASES: tuple[tuple[str, str, str, list[str]], ...] = (
    (
        "resource-id form: account is the fifth field",
        "docs/example.md",
        "arn:aws:sns:us-east-1:123456789012:example-topic",
        ["123456789012"],
    ),
    (
        "resource-type/resource-id form",
        "docs/example.md",
        "arn:aws:iam::123456789012:role/Example",
        ["123456789012"],
    ),
    (
        "resource-type:resource-id form",
        "docs/example.md",
        "arn:aws:states:us-east-1:123456789012:execution:Example:run-1",
        ["123456789012"],
    ),
    (
        "a partition other than aws parses the same way",
        "docs/example.md",
        "arn:aws-us-gov:ec2:us-gov-west-1:111122223333:volume/vol-0abcd",
        ["111122223333"],
    ),
    (
        "an empty account field proves nothing",
        "docs/example.md",
        "arn:aws:s3:::my-internal-bucket and arn:aws:health:us-west-2::event/XYZ",
        [],
    ),
    (
        "the literal aws in the account field proves nothing",
        "docs/example.md",
        "arn:aws:iam::aws:policy/ReadOnlyAccess",
        [],
    ),
    (
        "a redaction suffix in the account field is stripped",
        "docs/example.md",
        "arn:aws:iam::012345678901_3:role/Example",
        ["012345678901"],
    ),
    (
        "a wildcard region still yields the account, as an IAM policy writes it",
        "skills/example/references/iam-policy.json",
        '{"Resource": "arn:aws:logs:*:123456789012:log-group:/aws/lambda/x:*"}',
        ["123456789012"],
    ),
    (
        "a wildcard in the partition or the account field yields nothing",
        "skills/example/references/iam-policy.json",
        '{"Resource": ["arn:*:s3:*:*:accesspoint/example", "arn:aws:iam::*:role/X"]}',
        [],
    ),
    (
        "a template expression in the region still yields the account beside it",
        "mcp/example/template.yaml",
        "      - !Sub arn:aws:lambda:${AWS::Region}:123456789012:layer:Example:24",
        ["123456789012"],
    ),
    (
        "a template expression in the account field itself yields nothing",
        "mcp/example/template.yaml",
        "      - !Sub arn:aws:iam::${AWS::AccountId}:role/Example",
        [],
    ),
    (
        "ARNs are read in any file type, journal fields are not",
        "evals/benchmark.json",
        '{"cluster": "arn:aws:eks:us-east-1:111122223333:cluster/example",'
        ' "aws_account_id": "123456789012"}',
        ["111122223333"],
    ),
    (
        "the aws_account_id field of a journal, in a parsed tool input",
        "outputs/journal_records.json",
        '[{"content": "{\\"input\\": {\\"aws_account_id\\": \\"123456789012\\"}}"}]',
        ["123456789012"],
    ),
    (
        "the aws_account_id field of a journal, in agent prose",
        "outputs/journal_records.json",
        '[{"content": "I queried aws_account_id `111122223333` for events."}]',
        ["111122223333"],
    ),
    (
        "a twelve-digit object key under a tool_summary block, nested twice",
        "outputs/journal_records.json",
        '[{"content": "{\\"block_type\\": \\"tool_summary\\", \\"content\\": '
        '[{\\"type\\": \\"tool_result\\", \\"content\\": [{\\"text\\": '
        '\\"{\\\\\\"123456789012\\\\\\": {\\\\\\"DBInstances\\\\\\": []}}\\"}]}]}"}]',
        ["123456789012"],
    ),
    (
        "the same key outside a tool_summary block proves nothing",
        "outputs/journal_records.json",
        '[{"content": "{\\"block_type\\": \\"load_skill\\", \\"content\\": '
        '{\\"123456789012\\": {}}}"}]',
        [],
    ),
    (
        "a journal that will not parse falls back to the field pattern",
        "outputs/journal_records.json",
        '[{"content": "{\\"aws_account_id\\": \\"111122223333\\"',
        ["111122223333"],
    ),
)

# (label, file path, whole file text, added line, finding values expected)
#
# Run with an empty allowlist, so a placeholder behaves as a real account ID
# would. The file text is the evidence pass's input and the added line is the
# reporting pass's, which is how a case can prove an account in an untouched
# part of a file and then report it where the pull request names it.
REPORTING_CASES: tuple[tuple[str, str, str, str, list[str]], ...] = (
    (
        "an ARN on an added line is reported whole, not just its account",
        "docs/report.md",
        "",
        "See arn:aws:iam::123456789012:role/Example for the trust policy.",
        ["arn:aws:iam::123456789012:role/Example"],
    ),
    (
        "an IAM policy resource with a wildcard region is reported whole",
        "skills/example/references/iam-policy.json",
        "",
        '      "Resource": "arn:aws:logs:*:123456789012:log-group:/aws/lambda/x:*"',
        ["arn:aws:logs:*:123456789012:log-group:/aws/lambda/x:*"],
    ),
    (
        "an account-less ARN is not reported",
        "docs/report.md",
        "",
        "Grant access to arn:aws:s3:::my-internal-bucket/*",
        [],
    ),
    (
        "a wildcard account field is not reported",
        "skills/example/references/iam-policy.json",
        "",
        '      "Resource": "arn:aws:iam::*:role/ExampleRole"',
        [],
    ),
    (
        "an ARN whose region is a template expression is reported whole",
        "mcp/example/template.yaml",
        "",
        "      - !Sub arn:aws:lambda:${AWS::Region}:123456789012:layer:Example:24",
        ["arn:aws:lambda:${AWS::Region}:123456789012:layer:Example:24"],
    ),
    (
        "an ARN whose account is a template expression is not reported",
        "mcp/example/template.yaml",
        "",
        "      - !Sub arn:aws:iam::${AWS::AccountId}:role/Example",
        [],
    ),
    (
        "an ARN naming the AWS-owned policy account is not reported",
        "docs/report.md",
        "",
        "Attach arn:aws:iam::aws:policy/ReadOnlyAccess to the role.",
        [],
    ),
    (
        "a second account inside an ARN's resource name is reported too",
        "docs/report.md",
        "arn:aws:eks:us-east-1:111122223333:cluster/example",
        "arn:aws:iam::123456789012:role/audit-for-111122223333",
        [
            "arn:aws:iam::123456789012:role/audit-for-111122223333",
            "111122223333",
        ],
    ),
    (
        "an account proved elsewhere in the file is reported bare in prose",
        "docs/report.md",
        "arn:aws:eks:us-east-1:111122223333:cluster/example",
        "The cluster runs in account 111122223333.",
        ["111122223333"],
    ),
    (
        "a proved account is reported with its redaction suffix too",
        "outputs/journal_records.json",
        '[{"content": "{\\"aws_account_id\\": \\"012345678901\\"}"}]',
        '{"message": "events for 012345678901_2"}',
        ["012345678901_2"],
    ),
    (
        "twelve digits nothing proved are not reported",
        "docs/report.md",
        "arn:aws:s3:::my-internal-bucket",
        "A different number entirely: 123456789012.",
        [],
    ),
    # The five shapes the old twelve-digit rule reported, plus a thirteen-digit
    # epoch. Each one carries the placeholder's digits and no evidence at all,
    # so what keeps it silent is the thing this change introduced: nothing
    # proved those digits. Each illustration is synthetic — a UUID of repeated
    # letters, a round datestamp, a counter of zeros — rather than an instance
    # copied out of the repository's committed eval output, since a real
    # resource name in this file would outlive the pull request that cited it.
    (
        "the last group of a UUID is not an account ID",
        "docs/report.md",
        "",
        "execution aaaaaaaa-bbbb-cccc-dddd-123456789012 finished",
        [],
    ),
    (
        "the fractional digits of a decimal are not an account ID",
        "outputs/metrics.json",
        "",
        '{"latency": 46526.123456789012}',
        [],
    ),
    (
        "the integer part of a decimal is not an account ID",
        "outputs/metrics.json",
        "",
        '{"bytes": 123456789012.7833}',
        [],
    ),
    (
        "a YYYYMMDDHHMM datestamp in a resource name is not an account ID",
        "docs/report.md",
        "",
        "job nightly-training-run-200001010000 completed",
        [],
    ),
    (
        "a zero-padded counter is not an account ID",
        "outputs/events.json",
        "",
        '{"destinationId": "destinationId-000000000001"}',
        [],
    ),
    (
        "a thirteen-digit millisecond timestamp is not an account ID",
        "docs/report.md",
        "",
        "recorded at 1234567890123",
        [],
    ),
    # This one does exercise the boundary lookarounds: the file proves the
    # account through an ARN, and the added line holds the same digits inside a
    # longer hexadecimal resource id, where they belong to the id and name no
    # account. The ENI id is built from the placeholder for the same reason as
    # above.
    (
        "a proved account's digits inside a longer hex id are not reported",
        "docs/report.md",
        "arn:aws:ec2:us-east-1:123456789012:instance/example",
        "the interface eni-0123456789012abcd is attached",
        [],
    ),
    (
        "an instance ID needs no evidence",
        "docs/report.md",
        "",
        "Instance i-1234567890abcdef0 stopped responding.",
        ["i-1234567890abcdef0"],
    ),
    (
        "an AMI id is not an instance id",
        "docs/report.md",
        "",
        "Launched from ami-0abcdef1234567890 in the same subnet.",
        [],
    ),
)


def self_check(accounts: set[str], instances: set[str]) -> list[str]:
    """Confirm the two passes behave and every allowlist entry is suppressed.

    Three groups of cases, all covering failures that are silent — they stop
    identifiers from being *reported* rather than start reporting things
    falsely, so a passing check is the only symptom and no pull request reveals
    them.

    EXTRACTION_CASES pins the evidence pass: the three ARN resource forms, an
    account-less ARN, the ``aws`` account field, a non-``aws`` partition, the
    wildcard fields an IAM policy resource is written with, both journal fields
    including the nested and escaped ``tool_summary`` shape, and the redaction
    suffix.

    REPORTING_CASES pins the reporting pass end to end with an empty allowlist:
    an ARN reported whole, an IAM policy resource whose region is a wildcard
    reported whole as well, a proved account found bare in prose and with a
    suffix, an instance ID, and each of the five lookalike classes that used to
    be reported by the old twelve-digit shape rule and must now stay silent.
    Each case carries the file text the evidence pass reads and, separately, the
    added line the reporting pass reads, which is how a case can prove an
    account in a part of a file the pull request never touched and then see it
    reported where the pull request names it.

    The third group walks every entry in the allowlist in use. For an account ID
    it builds a file whose text is an ARN naming that entry, which is what makes
    the entry proved, and then an added line mentioning it bare; nothing may be
    reported, since the allowlist drops the entry from the proven set and
    suppresses the ARN as well. For an instance ID the ARN is inert — an
    instance ID in an account field is not twelve digits — and the added line is
    what matters. Both the bare and the ``_7``-suffixed form are tried, because
    the suffix is the part of the matching that is easiest to get wrong.

    Run it with ``--self-check``. It reads nothing but the allowlist and runs no
    ``git`` command.
    """
    failures: list[str] = []

    for label, path, text, expected_accounts in EXTRACTION_CASES:
        proven = sorted(extract_accounts([(path, text)]))
        if proven != sorted(expected_accounts):
            failures.append(
                f"evidence pass, {label}: proved {proven or 'nothing'}, "
                f"expected {sorted(expected_accounts) or 'nothing'}"
            )

    for label, path, text, line, expected_values in REPORTING_CASES:
        # An empty file text means the added line is the whole file, which is
        # how a real run sees a one-line addition: the line itself is part of
        # the evidence pass's input.
        documents = [(path, text or line)]
        proven = accounts_to_flag(documents, set())
        findings, _ = scan_added_lines(
            [(path, 1, line)], proven, set(), set(), set()
        )
        reported = sorted(finding.value for finding in findings)
        if reported != sorted(expected_values):
            failures.append(
                f"reporting pass, {label}: reported {reported or 'nothing'}, "
                f"expected {sorted(expected_values) or 'nothing'}"
            )

    for identifier in sorted(accounts | instances):
        for value in (identifier, f"{identifier}_7"):
            path = "docs/self-check.md"
            documents = [(path, f"arn:aws:iam::{identifier}:role/Example")]
            proven = accounts_to_flag(documents, accounts)
            findings, _ = scan_added_lines(
                [(path, 1, f"value {value} on a line")],
                proven,
                accounts,
                instances,
                set(),
            )
            if findings:
                failures.append(
                    f"allowlisted `{identifier}` was still reported as "
                    f"`{findings[0].value}` when written as `{value}`"
                )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
        "--allowlist",
        default=DEFAULT_ALLOWLIST,
        metavar="PATH",
        help=(
            "Allowlist of identifiers that are safe to publish, each with a "
            f"reason (default: {DEFAULT_ALLOWLIST}). A relative path is resolved "
            "against the repository root."
        ),
    )
    parser.add_argument(
        "--diff-file",
        default=None,
        metavar="PATH",
        help=(
            "Scan a saved unified diff instead of running git; `-` reads stdin. "
            "Intended for testing the scanner against a fixture. With a saved "
            "diff there is no head ref to read whole files from, so the "
            "evidence pass sees only the added lines."
        ),
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help=(
            "Scan nothing; instead run the scanner's own cases over the "
            "evidence pass, the reporting pass, and every allowlist entry both "
            "bare and with a `_N` redaction suffix, and exit non-zero if any "
            "fails."
        ),
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    allowlist = Path(args.allowlist)
    if not allowlist.is_absolute():
        allowlist = repo_root / allowlist

    accounts, instances, problems = load_allowlist(allowlist)
    for problem in problems:
        _error(problem)

    if args.self_check:
        if problems:
            return 2
        failures = self_check(accounts, instances)
        for failure in failures:
            _error(failure)
        total = len(accounts) + len(instances)
        print(
            f"Self-check: {len(EXTRACTION_CASES)} evidence case(s), "
            f"{len(REPORTING_CASES)} reporting case(s), {total} allowlist "
            f"entr(ies) bare and `_N`-suffixed, {len(failures)} failure(s)."
        )
        return 1 if failures else 0

    if args.diff_file:
        diff_text = read_diff_file(args.diff_file)
    else:
        diff_text = read_diff(repo_root, args.base_ref, args.head_ref)
    if diff_text is None:
        return 2

    entries = added_lines(diff_text)
    if not entries:
        print("This pull request adds no lines; nothing to scan.")
        _write_summary([], [], problems)
        return 2 if problems else 0

    # Evidence first, over the whole of every changed file; then reporting, over
    # the added lines alone. A saved diff has no ref to read files from, so the
    # evidence pass narrows to the added lines there.
    documents = changed_file_documents(
        repo_root,
        None if args.diff_file else args.head_ref,
        changed_paths(diff_text),
        entries,
    )
    proven_accounts = accounts_to_flag(documents, accounts)

    findings, warnings = scan_added_lines(
        entries,
        proven_accounts,
        accounts,
        instances,
        _excluded_paths(repo_root, allowlist),
    )

    for finding in findings[:MAX_PRINTED_FINDINGS]:
        print(
            f"FOUND  {finding.path}:{finding.line}  {finding.kind}  {finding.value}"
        )
    remainder = len(findings) - MAX_PRINTED_FINDINGS
    if remainder > 0:
        print(f"       … and {remainder} more finding(s) not printed.")

    for warning in warnings:
        _warn(warning)

    _annotate(findings, warnings)
    _write_summary(findings, warnings, problems)

    print(
        f"\n{len(documents)} changed file(s) read for evidence: "
        f"{len(proven_accounts)} account ID(s) proved and not allowlisted.",
        file=sys.stderr,
    )
    print(
        f"{len(entries)} added line(s) scanned: {len(findings)} finding(s).",
        file=sys.stderr,
    )

    if problems:
        print(
            f"\nThe allowlist `{DEFAULT_ALLOWLIST}` is broken, so no identifier was "
            "allowed. Fix the problems reported above and re-run.",
            file=sys.stderr,
        )
        return 2
    if findings:
        print(f"\n{REMEDIATION}", file=sys.stderr)
        return 1

    print("No AWS account IDs or EC2 instance IDs were added by this pull request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
