"""Append the upstream changes carried by API bump commits to release notes.

semantic-release only renders commit subjects, so a release made of API bumps
shows "bump hyundai_kia_connect_api X → Y" and nothing about what changed.
The bump commits written by bump_api_dependency.py hold the upstream notes in
their body; this collects them for every bump since the last stable release.

Usage: python scripts/release_notes.py < base_notes.md > release_notes.md
"""

from __future__ import annotations

import re
import subprocess
import sys

BUMP_SUBJECT_RE = re.compile(
    r"^\w+\(deps\)!?: bump hyundai_kia_connect_api (\S+) → (\S+)"
)
STABLE_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
SECTIONS = ("Features", "Bug Fixes")
# "- 5.1.2: * **eu:** text" -> "**eu:** text"
ITEM_PREFIX_RE = re.compile(r"^-\s+[\w.+-]+:\s+(?:\*\s+)?")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def last_stable_tag() -> str | None:
    """Latest vX.Y.Z tag on HEAD; beta tags sit off master and are skipped."""
    tags = [
        (tuple(int(p) for p in m.groups()), tag)
        for tag in _git("tag", "--merged", "HEAD").split()
        if (m := STABLE_TAG_RE.match(tag))
    ]
    return max(tags)[1] if tags else None


def bump_commit_messages(since: str | None) -> list[str]:
    """Full messages of the API bump commits after ``since``, oldest first."""
    rev = f"{since}..HEAD" if since else "HEAD"
    log = _git("log", "--reverse", "--format=%B%x1e", rev)
    messages = [m.strip() for m in log.split("\x1e")]
    return [m for m in messages if BUMP_SUBJECT_RE.match(m)]


def parse_bump_body(message: str) -> dict[str, list[str]]:
    """Section name -> upstream items, rejoining lines the squash merge wrapped."""
    sections: dict[str, list[str]] = {}
    items: list[str] | None = None
    for line in message.splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("###"):
            name = stripped.lstrip("#").strip()
            items = sections.setdefault(name, []) if name in SECTIONS else None
        elif not stripped:
            items = None
        elif items is not None:
            if stripped.startswith("- "):
                items.append(ITEM_PREFIX_RE.sub("", stripped))
            elif items:
                items[-1] += f" {stripped}"
    return sections


def api_changes(messages: list[str]) -> str:
    """Markdown block of upstream changes, or "" when there are none."""
    if not messages:
        return ""
    first = BUMP_SUBJECT_RE.match(messages[0])
    last = BUMP_SUBJECT_RE.match(messages[-1])
    assert first and last
    merged: dict[str, list[str]] = {name: [] for name in SECTIONS}
    for message in messages:
        for name, items in parse_bump_body(message).items():
            merged[name].extend(i for i in items if i not in merged[name])
    if not any(merged.values()):
        return ""
    lines = [
        f"### hyundai_kia_connect_api {first.group(1)} → {last.group(2)}",
        "",
    ]
    for name in SECTIONS:
        if merged[name]:
            lines.extend([f"#### {name}", "", *(f"* {i}" for i in merged[name]), ""])
    return "\n".join(lines).rstrip()


def main() -> int:
    notes = sys.stdin.read().rstrip()
    extra = api_changes(bump_commit_messages(last_stable_tag()))
    print(f"{notes}\n\n{extra}" if notes and extra else notes or extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
