#!/usr/bin/env python3
"""Detect stale skills and emit a freshness-reminder report.

A skill is "stale" when its directory has had no git commit for at least
``--max-age-days`` (default 60 days ~= 2 months). Freshness is measured from the
last commit that touched ``skills/<name>/`` — a real, always-present signal,
unlike CHANGELOG dates which are inconsistent across skills.

The script reads each ``skills/<name>/SKILL.md`` frontmatter for the ``author``
field (an internal alias, surfaced in the issue as plain text for a maintainer
to route to — it is NOT a GitHub login and is never mentioned or assigned) and
prints:

  * a human-readable summary to stderr, and
  * a JSON array of stale skills to stdout (or to ``--output`` / the file named
    by the ``GITHUB_OUTPUT``-style ``--output`` flag) for the workflow to consume.

Each stale entry has: ``id``, ``authors`` (list), ``last_commit_iso``,
``last_commit_sha``, ``age_days``.

Exit code is always 0 (a stale skill is not a failure); ``--fail-on-stale`` makes
it exit 1 when any skill is stale, for callers that want a hard gate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


FRONTMATTER_AUTHOR_RE = re.compile(r"^\s*author\s*:\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class StaleSkill:
    id: str
    authors: list[str]
    last_commit_iso: str
    last_commit_sha: str
    age_days: int


ISSUE_TITLE_PREFIX = "[skill-freshness] Verify"
WORKFLOW_PATH = ".github/workflows/skill-staleness-reminder.yml"


def issue_title(skill: StaleSkill) -> str:
    return f"{ISSUE_TITLE_PREFIX} `{skill.id}` is still current"


def issue_body(skill: StaleSkill, max_age_days: int) -> str:
    # The frontmatter `author` is the skill's declared owner, but in this repo it
    # is an internal alias, NOT a GitHub login (e.g. "hokang" -> GitHub user
    # "howard-m-k"). So it is surfaced as plain text for a maintainer to route to,
    # never @-mentioned or used as an assignee.
    listed_author = ", ".join(f"`{a}`" for a in skill.authors) or (
        "_none listed in SKILL.md frontmatter_"
    )
    return "\n".join(
        [
            f"The **`{skill.id}`** skill has not been updated in "
            f"**{skill.age_days} days** (last commit `{skill.last_commit_iso}`), "
            f"which exceeds the {max_age_days}-day freshness window.",
            "",
            f"**Listed author (SKILL.md frontmatter):** {listed_author}",
            "",
            "A maintainer has been assigned to triage this. Please confirm the skill "
            "is still current, or reassign to the author above (or whoever now owns the "
            "skill) to verify:",
            "",
            "- [ ] AWS APIs, CLI commands, and console paths referenced are still valid",
            "- [ ] Thresholds, defaults, and version numbers still reflect current AWS behavior",
            "- [ ] Documentation links in the skill and its `references/` still resolve",
            "- [ ] Evals still pass (`.skilleval.yaml` / `evals/`)",
            "",
            "**If it's still accurate:** bump the patch version in `SKILL.md` frontmatter "
            "and add a `CHANGELOG.md` line noting the freshness review (a commit touching "
            f"`skills/{skill.id}/` resets the clock and closes this reminder next cycle).",
            "",
            "**If it needs changes:** open a PR with the updates.",
            "",
            f"_Generated automatically by the Skill Staleness Reminder workflow "
            f"(`{WORKFLOW_PATH}`). It reopens on the next scheduled run if the skill "
            "is still untouched._",
        ]
    )


def _repo_root() -> Path:
    """Resolve the repository root from this script's location (.github/scripts/)."""
    return Path(__file__).resolve().parents[2]


def _parse_authors(skill_md: Path) -> list[str]:
    """Extract author handle(s) from a SKILL.md frontmatter block.

    Only the frontmatter (between the first pair of ``---`` fences) is scanned so
    a stray ``author:`` in prose can't be picked up. Handles a single value or a
    comma-separated list, strips surrounding quotes, and drops a leading ``@``.
    """
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return []
    end = text.find("---", 3)
    if end == -1:
        return []
    frontmatter = text[3:end]

    m = FRONTMATTER_AUTHOR_RE.search(frontmatter)
    if not m:
        return []
    raw = m.group(1).strip().strip('"').strip("'")
    authors = []
    for part in raw.split(","):
        handle = part.strip().lstrip("@").strip()
        if handle:
            authors.append(handle)
    return authors


def _last_commit(repo_root: Path, rel_dir: str) -> tuple[datetime, str] | None:
    """Return (commit datetime UTC, short sha) of the last commit touching rel_dir.

    Returns None when the path has no commit history (e.g. a brand-new,
    uncommitted skill) — such skills are treated as fresh and skipped.
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cI%x09%h", "--", rel_dir],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    line = result.stdout.strip()
    if not line:
        return None
    iso, _, sha = line.partition("\t")
    # %cI is strict ISO 8601 with offset; normalize to aware UTC.
    dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
    return dt, sha


def find_stale_skills(repo_root: Path, max_age_days: int, now: datetime) -> list[StaleSkill]:
    skills_dir = repo_root / "skills"
    stale: list[StaleSkill] = []
    if not skills_dir.is_dir():
        return stale

    for skill_path in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_md = skill_path / "SKILL.md"
        if not skill_md.is_file():
            continue  # not a skill directory

        rel_dir = f"skills/{skill_path.name}"
        last = _last_commit(repo_root, rel_dir)
        if last is None:
            continue  # uncommitted / no history -> treat as fresh

        last_dt, sha = last
        age_days = (now - last_dt).days
        if age_days >= max_age_days:
            stale.append(
                StaleSkill(
                    id=skill_path.name,
                    authors=_parse_authors(skill_md),
                    last_commit_iso=last_dt.date().isoformat(),
                    last_commit_sha=sha,
                    age_days=age_days,
                )
            )
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=60,
        help="Age threshold in days; skills untouched this long are stale (default: 60 ~= 2 months).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the JSON array to this file (in addition to stdout).",
    )
    parser.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit 1 if any skill is stale (default: always exit 0).",
    )
    parser.add_argument(
        "--render-dir",
        type=Path,
        default=None,
        help=(
            "Write ready-to-post issue files into this directory: one "
            "<skill-id>.title and <skill-id>.body per stale skill, plus an "
            "index.txt listing the stale skill ids. Lets the workflow post "
            "issues without fragile shell heredocs."
        ),
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    now = datetime.now(timezone.utc)
    stale = find_stale_skills(repo_root, args.max_age_days, now)

    payload = json.dumps([asdict(s) for s in stale], indent=2)
    print(payload)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")

    if args.render_dir is not None:
        args.render_dir.mkdir(parents=True, exist_ok=True)
        for s in stale:
            (args.render_dir / f"{s.id}.title").write_text(
                issue_title(s), encoding="utf-8"
            )
            (args.render_dir / f"{s.id}.body").write_text(
                issue_body(s, args.max_age_days) + "\n", encoding="utf-8"
            )
        (args.render_dir / "index.txt").write_text(
            "".join(f"{s.id}\n" for s in stale), encoding="utf-8"
        )

    if stale:
        print(
            f"\n{len(stale)} skill(s) not updated in >= {args.max_age_days} days:",
            file=sys.stderr,
        )
        for s in stale:
            who = ", ".join(f"@{a}" for a in s.authors) or "(no author in frontmatter)"
            print(
                f"  - {s.id}: last commit {s.last_commit_iso} "
                f"({s.age_days}d ago, {s.last_commit_sha}) -> {who}",
                file=sys.stderr,
            )
    else:
        print(
            f"\nAll skills updated within the last {args.max_age_days} days.",
            file=sys.stderr,
        )

    if args.fail_on_stale and stale:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
