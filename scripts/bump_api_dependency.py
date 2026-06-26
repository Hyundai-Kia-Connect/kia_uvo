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


def _classify_single_release(body: str) -> tuple[str, dict[str, list[str]]]:
    body = body or ""
    sections: dict[str, list[str]] = {
        "breaking": [],
        "features": [],
        "fixes": [],
        "other": [],
    }
    level = "chore"

    if re.search(r"BREAKING CHANGE", body, re.IGNORECASE):
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
) -> tuple[str, str]:
    aggregate: dict[str, list[str]] = {
        "breaking": [],
        "features": [],
        "fixes": [],
        "other": [],
    }
    level = "chore"

    for release in releases:
        tag = release["tag_name"].lstrip("vV")
        body = release.get("body") or ""
        rel_level, sections = _classify_single_release(body)
        if rel_level != "chore":
            level = max(
                level, rel_level, key=["chore", "fix", "feat", "breaking"].index
            )
        for key in aggregate:
            for item in sections.get(key, []):
                aggregate[key].append(f"- {tag}: {item}")

    first = releases[0]["tag_name"].lstrip("vV")
    last = releases[-1]["tag_name"].lstrip("vV")
    included = ", ".join(r["tag_name"].lstrip("vV") for r in releases)

    body_lines = [
        f"Bump `{PACKAGE_NAME}` from `{first}` to `{last}`.",
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
    manifest_path = (
        sys.argv[1] if len(sys.argv) > 1 else "custom_components/kia_uvo/manifest.json"
    )
    token = os.environ.get("GITHUB_TOKEN")

    current_pin = get_current_pin(manifest_path)
    releases = list_releases_after(API_OWNER, API_REPO, current_pin, token)

    if not releases:
        print(json.dumps({"noop": True, "reason": "already at latest version"}))
        return 0

    commit_type, commit_body = classify_release_notes(releases)
    target_version = releases[-1]["tag_name"].lstrip("vV")
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
