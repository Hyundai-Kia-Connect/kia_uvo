"""Helper to bump hyundai_kia_connect_api with semantic release notes."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_OWNER = "Hyundai-Kia-Connect"
API_REPO = "hyundai_kia_connect_api"
BRANCH_NAME = "chore/bump-api-dependency"
PACKAGE_NAME = "hyundai_kia_connect_api"


def _http_get(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def get_current_pin(manifest_path: str) -> str:
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for req in data.get("requirements", []):
        match = re.search(rf"{re.escape(PACKAGE_NAME)}==([^\s\"]+)", req)
        if match:
            return match.group(1)
    raise ValueError(f"{PACKAGE_NAME} not found in {manifest_path} requirements")


def _version_key(tag: str) -> tuple[int, ...]:
    clean = tag.lstrip("vV")
    parts = clean.split(".")
    return tuple(int(p) for p in parts[:3])


def _fetch_releases(owner: str, repo: str, token: str | None) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100"
    return _http_get(url, token)


def _fetch_compare(
    owner: str, repo: str, base: str, head: str, token: str | None
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base}...{head}"
    return _http_get(url, token)


def _tag_name(version_or_tag: str) -> str:
    return (
        version_or_tag
        if version_or_tag.lower().startswith("v")
        else f"v{version_or_tag}"
    )


def _normalize_issue_refs(body: str, owner: str, repo: str) -> str:
    """Qualify issue/PR references so they survive a cross-repo paste.

    API release notes are written in the API repo's context: ``#123`` and
    ``[#123](url)`` point at API issues/PRs. ``jossef/action-semantic-release-info``
    (used by kia_uvo's release workflow) regenerates unqualified ``[#NNN]``
    references using the *release* repo's URL template, discarding the original
    explicit URL — so ``[#1156](api-url)`` in the bump commit body becomes
    ``[#1156](kia_uvo-url)`` in the kia_uvo release notes. Cross-repo-qualified
    refs (``other-repo#NNN``) are left intact by the writer.

    This helper rewrites every unqualified reference to ``owner/repo#NNN`` so the
    writer treats it as cross-repo and does not rewrite the URL:

      - ``[#NNN](url)``  -> ``[owner/repo#NNN](url)``  (keep URL, qualify text)
      - ``[#NNN]``       -> ``[owner/repo#NNN]``
      - plain ``#NNN``   -> ``owner/repo#NNN``

    Left untouched: already-qualified refs (``owner/repo#NNN``,
    ``other-repo#NNN``), and ``#`` anchors inside a github URL path
    (``.../issues/123#comment``).
    """
    repo_ref = f"{owner}/{repo}"

    # [#NNN](url) -> [owner/repo#NNN](url)
    body = re.sub(
        r"\[#(\d+)\]\(([^)]*)\)",
        lambda m: f"[{repo_ref}#{m.group(1)}]({m.group(2)})",
        body,
    )

    # [#NNN] without a following URL -> [owner/repo#NNN]
    body = re.sub(
        r"\[(#\d+)\](?!\()",
        lambda m: f"[{repo_ref}{m.group(1)}]",
        body,
    )

    # Plain #NNN, but not if it is already part of another repo's qualified ref
    # (other-repo#NNN) or a URL anchor (.../issues/123#comment).
    def _replace_plain(match: re.Match[str]) -> str:
        start = match.start()
        char_before = body[start - 1] if start > 0 else ""
        # Part of a qualified ref like owner/repo#NNN or other-repo#NNN?
        if re.match(r"[\w.-]", char_before):
            return match.group(0)
        # Anchor inside a github.com URL path (e.g. /issues/123#comment).
        window = body[max(0, start - 40) : start]
        if re.search(r"github\.com/.+/(issues|pull)/\d+$", window):
            return match.group(0)
        return f"{repo_ref}{match.group(0)}"

    return re.sub(r"#(\d+)", _replace_plain, body)


def _synthesize_body_from_commits(
    commits: list[dict[str, Any]], owner: str = API_OWNER, repo: str = API_REPO
) -> str:
    feat: list[str] = []
    fix: list[str] = []
    other: list[str] = []
    breaking = False

    for commit in commits:
        message = commit.get("commit", {}).get("message", "").split("\n")[0].strip()
        if not message:
            continue
        lower = message.lower()
        if "breaking change" in lower or "breaking changes" in lower:
            breaking = True
        if lower.startswith("feat") or lower.startswith("fix"):
            clean = re.sub(
                r"^(feat|fix)(?:\([^)]+\))?!?:\s*", "", message, flags=re.IGNORECASE
            )
            (feat if lower.startswith("feat") else fix).append(clean)
        else:
            clean = re.sub(
                r"^(chore|docs|ci|test)(?:\([^)]+\))?!?:\s*",
                "",
                message,
                flags=re.IGNORECASE,
            )
            other.append(clean)

    lines: list[str] = []
    if breaking:
        lines.append("BREAKING CHANGES")
    if feat:
        lines.append("### Features")
        lines.extend(_normalize_issue_refs(line, owner, repo) for line in feat)
    if fix:
        lines.append("### Bug Fixes")
        lines.extend(_normalize_issue_refs(line, owner, repo) for line in fix)
    if not feat and not fix and other:
        lines.append("### Other Changes")
        lines.extend(_normalize_issue_refs(line, owner, repo) for line in other)
    return "\n".join(lines)


def list_releases_after(
    owner: str, repo: str, current_pin: str, token: str | None
) -> list[dict[str, Any]]:
    releases = _fetch_releases(owner, repo, token)
    current_key = _version_key(current_pin)
    newer = [r for r in releases if _version_key(r["tag_name"]) > current_key]
    return sorted(newer, key=lambda r: _version_key(r["tag_name"]))


def _extract_section(body: str, headings: list[str]) -> str:
    if not body:
        return ""
    lines = body.splitlines()
    collected: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if any(lower.startswith(h.lower()) for h in headings):
            inside = True
            continue
        if inside and stripped.startswith("#"):
            break
        if inside and stripped:
            collected.append(stripped)
    return "\n".join(collected)


def _classify_single_release(
    body: str, owner: str = API_OWNER, repo: str = API_REPO
) -> tuple[str, dict[str, list[str]]]:
    body = _normalize_issue_refs(body or "", owner, repo)
    sections: dict[str, list[str]] = {
        "breaking": [],
        "features": [],
        "fixes": [],
        "other": [],
    }
    level = "chore"

    if re.search(
        r"BREAKING CHANGES?\b|^[#]+\s*BREAKING\b",
        body,
        re.IGNORECASE | re.MULTILINE,
    ):
        level = "breaking"
        sections["breaking"].append("Release notes indicate a breaking change.")

    features = _extract_section(body, ["### Features", "## Features"]).splitlines()
    if features and features[0]:
        level = max(level, "feat", key=["chore", "fix", "feat", "breaking"].index)
        sections["features"].extend(features)

    fixes = _extract_section(body, ["### Bug Fixes", "## Bug Fixes"]).splitlines()
    if fixes and fixes[0]:
        level = max(level, "fix", key=["chore", "fix", "feat", "breaking"].index)
        sections["fixes"].extend(fixes)

    other = _extract_section(
        body, ["### Other Changes", "## Other Changes"]
    ).splitlines()
    if other and other[0]:
        sections["other"].extend(other)

    if not any(sections.values()):
        sections["other"].append("No categorized release notes.")

    return level, sections


def _commit_prefix(level: str) -> str:
    if level == "breaking":
        return "feat!(deps):"
    if level == "feat":
        return "feat(deps):"
    if level == "fix":
        return "fix(deps):"
    return "chore(deps):"


def classify_release_notes(
    releases: list[dict[str, Any]],
    current_pin: str,
    owner: str = API_OWNER,
    repo: str = API_REPO,
    token: str | None = None,
) -> tuple[str, str]:
    aggregate: dict[str, list[str]] = {
        "breaking": [],
        "features": [],
        "fixes": [],
        "other": [],
    }
    level = "chore"

    for i, release in enumerate(releases):
        tag = release["tag_name"].lstrip("vV")
        body = release.get("body") or ""
        if not body.strip():
            base = releases[i - 1]["tag_name"] if i > 0 else _tag_name(current_pin)
            try:
                compare = _fetch_compare(owner, repo, base, release["tag_name"], token)
                body = _synthesize_body_from_commits(compare.get("commits", []))
            except urllib.error.HTTPError:
                body = ""
        rel_level, sections = _classify_single_release(body, owner, repo)
        if rel_level != "chore":
            level = max(
                level, rel_level, key=["chore", "fix", "feat", "breaking"].index
            )
        for key in aggregate:
            for item in sections.get(key, []):
                aggregate[key].append(f"- {tag}: {item}")

    last = releases[-1]["tag_name"].lstrip("vV")
    included = ", ".join(r["tag_name"].lstrip("vV") for r in releases)

    body_lines = [
        f"Bump `{PACKAGE_NAME}` from `{current_pin}` to `{last}`.",
        "",
        f"Upstream versions included in this bump: {included}.",
        "",
    ]
    if aggregate["breaking"]:
        body_lines.extend(["### BREAKING CHANGES", *aggregate["breaking"], ""])
    if aggregate["features"]:
        body_lines.extend(["### Features", *aggregate["features"], ""])
    if aggregate["fixes"]:
        body_lines.extend(["### Bug Fixes", *aggregate["fixes"], ""])
    if aggregate["other"]:
        body_lines.extend(["### Other Changes", *aggregate["other"], ""])

    return level, "\n".join(body_lines).rstrip()


def update_manifest(manifest_path: str, new_version: str) -> None:
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    requirements = data.get("requirements", [])
    for i, req in enumerate(requirements):
        if PACKAGE_NAME in req:
            requirements[i] = f"{PACKAGE_NAME}=={new_version}"
            break
    else:
        requirements.append(f"{PACKAGE_NAME}=={new_version}")
    data["requirements"] = requirements
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    dry_run = "--noop" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--noop"]
    manifest_path = args[0] if args else "custom_components/kia_uvo/manifest.json"
    token = os.environ.get("GITHUB_TOKEN")

    current_pin = get_current_pin(manifest_path)
    releases = list_releases_after(API_OWNER, API_REPO, current_pin, token)

    if not releases:
        print(json.dumps({"noop": True, "reason": "already at latest version"}))
        return 0

    commit_type, commit_body = classify_release_notes(
        releases, current_pin, API_OWNER, API_REPO, token
    )
    target_version = releases[-1]["tag_name"].lstrip("vV")

    if not dry_run:
        update_manifest(manifest_path, target_version)

    commit_title = f"{_commit_prefix(commit_type)} bump {PACKAGE_NAME} {current_pin} → {target_version}"

    output = {
        "noop": False,
        "branch": BRANCH_NAME,
        "commit_title": commit_title,
        "commit_body": commit_body,
        "pr_title": commit_title,
        "pr_body": commit_body,
        "target_version": target_version,
        "current_pin": current_pin,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
