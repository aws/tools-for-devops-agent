#!/usr/bin/env python3
"""Validate the ``evals/`` layout of the skills a pull request touches.

Every skill is expected to ship the results of all three evaluation test types,
produced by the (internal) skill evaluation tool and committed as-is::

    evals/
    ├── evals.json                                       # required
    ├── structure/
    │   └── structure-tests-results-v<N>.json            # at least one
    ├── best-practices/
    │   └── v<N>/                                        # at least one complete
    │       ├── benchmark.json
    │       └── iteration-<n>/
    │           └── best-practices-tests-results.json
    └── functional/
        └── v<N>/                                        # at least one complete
            ├── benchmark.json
            ├── evals.json
            └── iteration-<n>/
                └── <scenario>/
                    ├── with_skill/functional-tests-results.json
                    └── without_skill/functional-tests-results.json

``<N>`` is one or more digits (``v1``, ``v12``, ...). A version directory counts
only when *all* of its listed contents are present, and a type passes when at
least one of its version directories is complete — an aborted run left behind
next to a good one is harmless, but a lone aborted run does not satisfy the check.

The assertions stop at that depth on purpose. Requiring anything deeper would
track a tool that is still evolving: iteration counts vary (1, 3 and 4 all appear
in the reference skill's history), scenario directory names come from the skill's
own ``evals.json``, and ``_metadata.json`` is present in all 20 recent runs but
absent from older ones — documented and left unchecked rather than pinned.

Several paths the tool writes are also excluded by ``skills/.gitignore`` and so
never reach a PR at all: the ``cli_debug/`` and ``sdk_debug/`` directories, and
``outputs/classified_output.json`` / ``outputs/metadata.json``. Of the outputs,
only ``journal_records.json`` is committed. See CONTRIBUTING.md.

Rollout is gradual, so a skill's *mode* decides whether a violation fails the
build or is only reported:

  * **enforced** — any of: the skill directory does not exist at the base ref (a
    skill the PR adds); it already carries the new layout at the base ref (so a
    migrated skill cannot regress); or the PR itself introduces the new layout
    (so a migration cannot land half-finished and fail the next person to touch
    the skill). Violations exit non-zero.
  * **legacy** — a pre-existing skill still on the old flat ``evals/`` layout,
    which this PR also leaves on that layout. Violations are reported as warnings
    only, until it is migrated.

Two things can override that per pull request, checked in this order:

  1. the ``enforce-evals`` label — every skill the PR touches is enforced,
     whatever its mode would otherwise be. A maintainer-only, per-PR form of
     ``--strict``.
  2. ``PRS_PREDATING_CHECK`` — pull requests already open when this check was
     introduced. Every skill they touch is legacy, including a skill the PR adds.
     This waives *producing* results only: a skill that already carries results at
     the base ref, or that the PR itself partly migrates, stays enforced.

Without either, the mode is derived as described above and nothing changes.

Only skills whose files the PR touches are inspected. Skill directories deleted
by the PR, and paths under ``skills/`` that are not skill directories (such as
``skills/.gitignore``), are skipped.

A skill promotes itself from legacy to enforced as soon as its migration lands on
the base branch, so the split needs no maintenance as the backlog shrinks.
``--strict`` enforces on unmigrated legacy skills too, repo-wide, which is a lever
for *forcing* that migration — every PR touching a legacy skill becomes a blocker
— rather than a cleanup step to apply after the fact, when it would be a no-op. It
also overrides ``PRS_PREDATING_CHECK``.

A skill can be exempted from a test type it genuinely cannot produce results for,
by committing ``evals/exemptions.json``::

    {
      "functional": {
        "reason": "why these results cannot be produced"
      }
    }

An exempted test type is not checked; it is reported as a warning instead, so a
green check still shows what is missing and why. ``evals.json`` is hand-written
rather than tool output, so it is never exemptable. The file fails closed: bad
JSON, an unknown test type, or a missing/empty ``reason`` grants no exemption and
is itself reported, so a typo cannot silently waive a requirement. Because the
file lives in the PR diff, granting an exemption goes through the same review as
any other change.

Exit code is 0 when no enforced skill has violations, 1 otherwise. Exemptions
never affect the exit code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


STRUCTURE_RESULT_RE = re.compile(r"^structure-tests-results-v\d+\.json$")
VERSION_DIR_RE = re.compile(r"^v\d+$")

# Presence of any of these at the base ref means the skill has been migrated to
# the new layout, so it is held to it from then on.
MIGRATED_MARKERS = ("evals/structure", "evals/best-practices", "evals/functional")

# Pull requests that were already open when this check was introduced, and that
# touch a skill directory. Their authors tested their skills against the rules that
# existed when they contributed, so every skill these PRs touch is treated as
# legacy — a skill the PR *adds* included, which is what matters in practice, since
# all of these PRs contribute new skills.
#
# This does not let them through unconditionally: a maintainer opts an individual
# PR back into enforcement with the ``ENFORCE_LABEL``, checked first. The list on its
# own was considered too open: it would waive the requirement for whatever these
# PRs end up containing, and the only way back would be another change to this
# script.
#
# The list is finite and stops mattering as these PRs close; a number that is no
# longer open is simply never matched. Delete the list and ``--pr-number`` once all
# of them are closed.
#
# Re-derive it immediately before merging, since a PR opened in the meantime is also
# one whose author could not have known about this check:
#
#   for n in $(gh pr list --state open --limit 100 --json number --jq '.[].number'); do
#     gh api "repos/aws/tools-for-devops-agent/pulls/$n/files" --paginate --jq '.[].filename' \
#       | awk -F/ -v n="$n" '$1=="skills" && NF>=3 {print n; exit}'
#   done | sort -n | paste -sd, -
#
# Use the files endpoint, not ``gh pr diff --name-only``: that fails with HTTP 406 on a
# diff over 20,000 lines *and still exits 0*, so a large PR is skipped without a word.
# A skill PR shipping a full eval tree is exactly the kind that trips it — #97 has 256
# files and was missed this way on the first pass.
#
# Entries are included on the factual test (open, touches a skill directory), not on
# whether being listed changes that PR's outcome. A PR already shipping the new layout
# is enforced regardless, since ``now_migrated`` overrides this list, so its entry does
# nothing today — but it starts mattering if that PR is restructured before merge, and
# judging entries by outcome is what makes the list wrong later.
#
# Last derived 2026-09-21.
PRS_PREDATING_CHECK = frozenset(
    {
        20, 25, 26, 38, 42, 54, 56, 58, 62, 67,
        71, 72, 77, 78, 81, 85, 89, 90, 91, 93,
        94, 96, 97, 98, 99,
    }
)

# Label that forces enforcement on every skill a pull request touches, whatever the
# derived mode. Deliberately *not* the `needs-evals` label the companion labeling
# workflow manages: that one is removed as soon as the check passes, so reusing it
# would discard the decision at exactly the wrong moment — the next push could then
# delete the results again and go green. This label is never written by automation.
#
# Adding or removing a label requires triage or write access to this repository, so
# a contributor cannot clear it to unblock their own pull request.
ENFORCE_LABEL = "enforce-evals"

# Test types whose results a skill can be exempted from, via evals/exemptions.json.
# ``evals.json`` is hand-written and always required, so it is not exemptable.
EXEMPTABLE_TYPES = ("structure", "best-practices", "functional")
EXEMPTIONS_FILENAME = "exemptions.json"

DOCS_HINT = (
    'See the "Eval Results Layout" section of CONTRIBUTING.md for the expected '
    "evals/ layout."
)

# Printed when a pull request predating the check has violations, so a maintainer
# reading a green check can see what was let through and how to require it instead.
PREDATES_CHECK_HINT = (
    "The skill(s) above were reported as warnings because this pull request was "
    "already open when the eval results check was introduced. To require the "
    f"results anyway, apply the `{ENFORCE_LABEL}` label to this pull request; that "
    "re-runs the check with every touched skill enforced."
)


@dataclass
class SkillReport:
    id: str
    enforced: bool
    # Why the mode was overridden, when it was ("predates check", or the name of the
    # thing that forced enforcement). Empty when the mode was derived normally.
    # Reported so a green check still shows that a skill was let through, and a red
    # one shows what made it strict.
    mode_note: str = ""
    violations: list[str] = field(default_factory=list)
    # Granted exemptions, surfaced as warnings so they stay visible on a green
    # check rather than disappearing. Kept out of ``violations`` so they are never
    # counted as failures themselves; the exempted requirement is simply not
    # checked, which is what lets an otherwise-failing skill exit 0.
    exemptions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def mode(self) -> str:
        """Human-readable mode, including why it was overridden."""
        base = "enforced" if self.enforced else "legacy"
        return f"{base} ({self.mode_note})" if self.mode_note else base


def _repo_root() -> Path:
    """Resolve the repository root from this script's location (.github/scripts/)."""
    return Path(__file__).resolve().parents[2]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True
    )


def _exists_at_ref(repo_root: Path, ref: str, path: str) -> bool:
    """True when ``path`` (file or directory) exists in the tree at ``ref``."""
    return _git(repo_root, "cat-file", "-e", f"{ref}:{path}").returncode == 0


def _diff_base(repo_root: Path, base_ref: str, head_ref: str) -> str:
    """Return the merge base of base_ref and head_ref, or base_ref if unavailable.

    Using the merge base means changes that landed on the base branch after the
    PR branched are not attributed to this PR.
    """
    result = _git(repo_root, "merge-base", base_ref, head_ref)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    print(
        f"warning: no merge base between {base_ref} and {head_ref}; "
        f"diffing against {base_ref} directly",
        file=sys.stderr,
    )
    return base_ref


def changed_skill_ids(repo_root: Path, base: str, head_ref: str) -> list[str]:
    """Skill ids under skills/ touched between ``base`` and ``head_ref``.

    Only directories that still exist in the working tree and contain a SKILL.md
    are returned, which drops deleted/renamed-away skills and non-skill paths
    such as ``skills/.gitignore``.
    """
    result = _git(repo_root, "diff", "--name-only", base, head_ref)
    if result.returncode != 0:
        raise SystemExit(
            f"git diff {base} {head_ref} failed: {result.stderr.strip()}"
        )

    ids: list[str] = []
    for line in result.stdout.splitlines():
        parts = Path(line.strip()).parts
        if len(parts) < 3 or parts[0] != "skills":
            continue  # not a file inside a skill directory
        skill_id = parts[1]
        if skill_id in ids:
            continue
        skill_path = repo_root / "skills" / skill_id
        if not skill_path.is_dir():
            continue  # deleted or renamed away by this PR
        if not (skill_path / "SKILL.md").is_file():
            continue  # not a skill directory
        ids.append(skill_id)
    return sorted(ids)


def _version_dirs(parent: Path) -> list[Path]:
    """``v<N>`` subdirectories of ``parent``, ordered numerically (v2 before v10)."""
    return sorted(
        (p for p in parent.iterdir() if p.is_dir() and VERSION_DIR_RE.match(p.name)),
        key=lambda p: int(p.name[1:]),
    )


def _missing_in_best_practices_version(version: Path) -> list[str]:
    """Required contents absent from one ``evals/best-practices/v<N>/`` directory."""
    missing = []
    if not (version / "benchmark.json").is_file():
        missing.append("benchmark.json")
    if not any(version.glob("iteration-*/best-practices-tests-results.json")):
        missing.append("iteration-<n>/best-practices-tests-results.json")
    return missing


def _missing_in_functional_version(version: Path) -> list[str]:
    """Required contents absent from one ``evals/functional/v<N>/`` directory.

    The with_skill / without_skill pair has to be satisfied by the *same* scenario
    directory: a functional run is only meaningful as a comparison of the two.
    Scenario directory names come from the skill's own evals.json, so they are
    matched as a wildcard.
    """
    missing = []
    if not (version / "benchmark.json").is_file():
        missing.append("benchmark.json")
    if not (version / "evals.json").is_file():
        missing.append("evals.json")

    paired = any(
        (scenario / "with_skill" / "functional-tests-results.json").is_file()
        and (scenario / "without_skill" / "functional-tests-results.json").is_file()
        for scenario in version.glob("iteration-*/*")
        if scenario.is_dir()
    )
    if not paired:
        missing.append(
            "iteration-<n>/<scenario>/{with_skill,without_skill}"
            "/functional-tests-results.json"
        )
    return missing


def _check_versioned_type(
    skill_id: str, evals: Path, name: str, missing_fn
) -> list[str]:
    """Require at least one complete ``v<N>/`` run under ``evals/<name>/``.

    "Complete" means ``missing_fn`` reports nothing for it. When no version
    qualifies, the message explains what the highest-numbered one lacks, since
    that is almost always the run the contributor meant to commit.
    """
    target = evals / name
    rel = f"skills/{skill_id}/evals/{name}"
    if not target.is_dir():
        return [f"missing directory `{rel}/`"]

    versions = _version_dirs(target)
    if not versions:
        others = sorted(p.name for p in target.iterdir() if p.is_dir())
        detail = f" (subdirectories found: {', '.join(others[:5])})" if others else ""
        return [f"`{rel}/` has no `v<number>/` directory{detail}"]

    missing_by_version = {v.name: missing_fn(v) for v in versions}
    if any(not m for m in missing_by_version.values()):
        return []  # at least one complete run

    latest = versions[-1].name
    lacks = ", ".join(f"`{m}`" for m in missing_by_version[latest])
    inspected = ", ".join(v.name for v in versions[-5:])
    more = f" (last 5 of {len(versions)}: {inspected})" if len(versions) > 5 else f" ({inspected})"
    return [
        f"`{rel}/` has no complete `v<number>/` run{more}; the latest, `{latest}/`, "
        f"is missing {lacks}"
    ]


def read_exemptions(evals: Path, rel_evals: str) -> tuple[dict[str, str], list[str]]:
    """Parse ``evals/exemptions.json``, returning ({test type: reason}, problems).

    Anything wrong with the file — bad JSON, an unknown test type, a missing or
    empty reason — is reported as a problem and grants no exemption. Failing
    closed matters here: a typo must not silently waive a requirement.
    """
    path = evals / EXEMPTIONS_FILENAME
    rel = f"{rel_evals}/{EXEMPTIONS_FILENAME}"
    if not path.is_file():
        return {}, []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {}, [f"`{rel}` is not valid JSON ({exc.__class__.__name__}: {exc})"]

    if not isinstance(raw, dict):
        return {}, [f"`{rel}` must be a JSON object keyed by test type"]

    exemptions: dict[str, str] = {}
    problems: list[str] = []
    for test_type, body in raw.items():
        if test_type not in EXEMPTABLE_TYPES:
            problems.append(
                f"`{rel}` has unknown test type `{test_type}` "
                f"(expected one of: {', '.join(EXEMPTABLE_TYPES)})"
            )
            continue
        reason = body.get("reason") if isinstance(body, dict) else None
        if not isinstance(reason, str) or not reason.strip():
            problems.append(
                f"`{rel}` entry `{test_type}` needs a non-empty `reason` explaining "
                "why the results cannot be produced"
            )
            continue
        exemptions[test_type] = reason.strip()

    return exemptions, problems


def validate_skill(repo_root: Path, skill_id: str) -> tuple[list[str], list[str]]:
    """Validate one skill, returning (violations, granted exemptions).

    An exempted test type is not checked at all; instead it is reported as a
    warning, so a green check still shows which results are missing and why.
    """
    skill_path = repo_root / "skills" / skill_id
    evals = skill_path / "evals"
    rel_evals = f"skills/{skill_id}/evals"

    if not evals.is_dir():
        return [f"missing directory `{rel_evals}/`"], []

    exemptions, violations = read_exemptions(evals, rel_evals)

    # Never exemptable: evals.json is hand-written, not tool output.
    if not (evals / "evals.json").is_file():
        violations.append(f"missing file `{rel_evals}/evals.json`")

    if "structure" not in exemptions:
        structure = evals / "structure"
        if not structure.is_dir():
            violations.append(f"missing directory `{rel_evals}/structure/`")
        elif not any(
            p.is_file() and STRUCTURE_RESULT_RE.match(p.name)
            for p in structure.iterdir()
        ):
            violations.append(
                f"`{rel_evals}/structure/` has no "
                "`structure-tests-results-v<number>.json` file"
            )

    if "best-practices" not in exemptions:
        violations += _check_versioned_type(
            skill_id, evals, "best-practices", _missing_in_best_practices_version
        )

    if "functional" not in exemptions:
        violations += _check_versioned_type(
            skill_id, evals, "functional", _missing_in_functional_version
        )

    granted = [
        f"`{test_type}` results exempted — {exemptions[test_type]}"
        for test_type in EXEMPTABLE_TYPES
        if test_type in exemptions
    ]
    return violations, granted


def build_reports(
    repo_root: Path,
    skill_ids: list[str],
    base: str,
    force_reason: str | None = None,
    predates_check: bool = False,
) -> list[SkillReport]:
    """Validate each touched skill and resolve its mode.

    ``force_reason`` names whatever is forcing enforcement (``--strict`` or the
    label) and is reported as-is; ``predates_check`` marks the pull request as one
    opened before this check existed. Precedence is force, then predates, then
    derived.
    """
    reports: list[SkillReport] = []
    for skill_id in skill_ids:
        rel_dir = f"skills/{skill_id}"
        is_new = not _exists_at_ref(repo_root, base, rel_dir)
        was_migrated = any(
            _exists_at_ref(repo_root, base, f"{rel_dir}/{marker}")
            for marker in MIGRATED_MARKERS
        )
        # Also enforce when the PR *itself* introduces the new layout, so a
        # migration cannot land half-finished. Without this, a PR adding only
        # evals/structure/ to a legacy skill would warn and merge, and the next
        # PR touching that skill — possibly by someone else, for an unrelated
        # reason — would fail on the two directories it never touched.
        now_migrated = any(
            (repo_root / rel_dir / marker).exists() for marker in MIGRATED_MARKERS
        )

        # Precedence: an explicit force wins, then a PR predating the check, then
        # the mode derived from the skill itself.
        #
        # Both migration conditions survive the predating-PR case, which only waives
        # producing results that were never asked for:
        #
        #  * ``was_migrated`` — predating the check does not license deleting results
        #    already on the base branch, so the anti-regression ratchet still holds.
        #    Unreachable today, since no skill on the base branch carries results
        #    yet, but a long-lived PR rebased onto a migrated skill could hit it.
        #  * ``now_migrated`` — a PR that ships *part* of the new layout still has to
        #    finish it (or exempt the rest). Otherwise the half migration lands, and
        #    the next person to touch that skill inherits a failure on directories
        #    they never touched — the trap ``now_migrated`` exists to prevent, which
        #    a PR predating the check would otherwise spring. None of the PRs in
        #    ``PRS_PREDATING_CHECK`` ships any of the marker directories, so this
        #    costs them nothing.
        if force_reason:
            enforced, mode_note = True, force_reason
        elif predates_check and not (was_migrated or now_migrated):
            enforced, mode_note = False, "predates check"
        else:
            enforced, mode_note = (is_new or was_migrated or now_migrated), ""

        violations, exemptions = validate_skill(repo_root, skill_id)
        reports.append(
            SkillReport(
                id=skill_id,
                enforced=enforced,
                mode_note=mode_note,
                violations=violations,
                exemptions=exemptions,
            )
        )
    return reports


def parse_label_names(raw: str) -> list[str]:
    """Label names from a JSON array, as produced by ``toJSON(...labels.*.name)``.

    Anything unparseable is reported and treated as "no labels". That direction is
    deliberate: the only label this script reads *adds* enforcement, so a mangled
    value can never waive a requirement — at worst a maintainer sees the label they
    applied did not take effect, with the reason in the log.
    """
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(
            f"warning: --labels is not valid JSON ({exc}); treating the pull "
            "request as unlabeled",
            file=sys.stderr,
        )
        return []
    if not isinstance(data, list):
        print(
            "warning: --labels must be a JSON array of label names; treating the "
            "pull request as unlabeled",
            file=sys.stderr,
        )
        return []
    return [name for name in data if isinstance(name, str)]


def _annotate(report: SkillReport) -> None:
    """Emit GitHub Actions annotations, one per violation.

    Deliberately emitted without a ``file=`` anchor. Every violation is about a
    path that is *absent*, and attaching the annotation to an existing file (the
    skill's SKILL.md was the only candidate present in the diff) wrongly implies
    that file is at fault. Without an anchor the annotation surfaces on the check
    and run summary instead of as an inline marker on an unrelated line.
    """
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    title = f"Skill evals layout: {report.id}"
    level = "error" if report.enforced else "warning"
    for violation in report.violations:
        # Annotations are single-line; strip any embedded newlines.
        message = violation.replace("\n", " ")
        print(f"::{level} title={title}::{message} — {DOCS_HINT}")
    # Exemptions are always warnings, never errors, even on an enforced skill.
    for exemption in report.exemptions:
        print(f"::warning title={title}::{exemption.replace(chr(10), ' ')}")


def _write_summary(reports: list[SkillReport], failed: list[SkillReport]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = ["## Skill evals layout check", ""]
    if not reports:
        lines.append("No skill directories touched by this PR. Nothing to check.")
    else:
        lines.append("| Skill | Mode | Result | Exemptions |")
        lines.append("| --- | --- | --- | --- |")
        for r in reports:
            mode = r.mode if r.enforced else f"{r.mode} — warn only"
            if r.ok:
                result = "pass"
            elif r.enforced:
                result = f"**fail** — {len(r.violations)} issue(s)"
            else:
                result = f"warn — {len(r.violations)} issue(s)"
            exempt = str(len(r.exemptions)) if r.exemptions else "—"
            lines.append(f"| `{r.id}` | {mode} | {result} | {exempt} |")
        lines.append("")
        for r in reports:
            if r.violations:
                heading = "Failures" if r.enforced else "Warnings"
                lines.append(f"### `{r.id}` — {heading}")
                lines += [f"- {v}" for v in r.violations]
                lines.append("")
            if r.exemptions:
                lines.append(f"### `{r.id}` — Exemptions granted")
                lines += [f"- {e}" for e in r.exemptions]
                lines.append("")
        if failed:
            lines.append(DOCS_HINT)
        if any(r.mode_note == "predates check" and not r.ok for r in reports):
            lines += ["", PREDATES_CHECK_HINT]

    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


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
        "--skill",
        action="append",
        default=None,
        metavar="ID",
        help=(
            "Validate this skill id instead of deriving the list from the diff. "
            "Repeatable; the named skills are always enforced. Useful locally."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail on unmigrated legacy skills too, instead of only warning. Use it "
            "to force migration: every PR touching a legacy skill becomes a "
            "blocker. Once all skills are migrated this flag has no effect. Also "
            "overrides the list of pull requests predating the check."
        ),
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Number of the pull request being checked, matched against "
            "PRS_PREDATING_CHECK. Omitted locally, where no PR is involved."
        ),
    )
    parser.add_argument(
        "--labels",
        default="",
        metavar="JSON",
        help=(
            "The pull request's label names as a JSON array. The "
            f"`{ENFORCE_LABEL}` label forces enforcement on every skill the PR "
            "touches."
        ),
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()

    # Precedence between these two is resolved in build_reports: force wins.
    if args.strict:
        force_reason = "--strict"
    elif ENFORCE_LABEL in parse_label_names(args.labels):
        force_reason = f"{ENFORCE_LABEL} label"
    else:
        force_reason = None
    predates_check = args.pr_number in PRS_PREDATING_CHECK

    if args.skill:
        reports = []
        for s in sorted(set(args.skill)):
            violations, exemptions = validate_skill(repo_root, s)
            reports.append(
                SkillReport(
                    id=s,
                    enforced=True,
                    mode_note="--skill",
                    violations=violations,
                    exemptions=exemptions,
                )
            )
    else:
        base = _diff_base(repo_root, args.base_ref, args.head_ref)
        skill_ids = changed_skill_ids(repo_root, base, args.head_ref)
        reports = build_reports(
            repo_root, skill_ids, base, force_reason, predates_check
        )

    if not reports:
        print("No skill directories touched by this PR; evals layout check skipped.")
        _write_summary(reports, [])
        return 0

    failed = [r for r in reports if r.enforced and not r.ok]
    warned = [r for r in reports if not r.enforced and not r.ok]

    for r in reports:
        if r.ok:
            print(f"PASS  {r.id} ({r.mode})")
        else:
            outcome = "FAIL" if r.enforced else "WARN"
            print(f"{outcome}  {r.id} ({r.mode})")
            for v in r.violations:
                print(f"        - {v}")
        for e in r.exemptions:
            print(f"        ! {e}")
        _annotate(r)

    _write_summary(reports, failed)

    print(
        f"\n{len(reports)} skill(s) checked: "
        f"{len(reports) - len(failed) - len(warned)} pass, "
        f"{len(failed)} fail, {len(warned)} warn.",
        file=sys.stderr,
    )

    if any(r.mode_note == "predates check" and not r.ok for r in reports):
        print(f"\n{PREDATES_CHECK_HINT}", file=sys.stderr)

    if failed:
        print(
            "\nMerging is blocked until the skill(s) above ship a complete evals/ "
            f"layout. {DOCS_HINT}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
