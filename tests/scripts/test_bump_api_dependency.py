import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from bump_api_dependency import (
    classify_release_notes,
    get_current_pin,
    main,
    update_manifest,
)


def test_get_current_pin(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": ["hyundai_kia_connect_api==4.21.0"]})
    )
    assert get_current_pin(str(manifest)) == "4.21.0"


def test_classify_release_notes_feat_and_fix():
    releases = [
        {"tag_name": "v4.22.0", "body": "### Features\n- add new sensor\n"},
        {"tag_name": "v4.23.0", "body": "### Bug Fixes\n- fix timeout\n"},
    ]
    commit_type, body = classify_release_notes(releases, "4.21.0")
    assert commit_type == "feat"
    assert "### Features" in body
    assert "- 4.22.0:" in body
    assert "### Bug Fixes" in body
    assert "- 4.23.0:" in body


def test_classify_release_notes_body_uses_current_pin_as_from():
    # Single skipped release: body must read "from <current_pin> to <last>",
    # not "from <last> to <last>" (regression guard for the "from" field).
    releases = [{"tag_name": "v4.22.1", "body": "### Bug Fixes\n- fix a bug\n"}]
    _commit_type, body = classify_release_notes(releases, "4.22.0")
    assert "from `4.22.0` to `4.22.1`" in body
    assert "from `4.22.1` to `4.22.1`" not in body


def test_classify_release_notes_breaking_heading():
    releases = [
        {
            "tag_name": "v4.22.0",
            "body": "### BREAKING CHANGES\n- drop legacy auth endpoint\n",
        }
    ]
    commit_type, body = classify_release_notes(releases, "4.21.0")
    assert commit_type == "breaking"
    assert "### BREAKING CHANGES" in body
    assert "- 4.22.0: Release notes indicate a breaking change." in body


def test_classify_release_notes_empty_body_uses_compare_commits(monkeypatch):
    releases = [{"tag_name": "v4.22.0", "body": ""}]

    def _fetch_compare(_owner, _repo, base, head, _token):
        assert base == "v4.21.0"
        assert head == "v4.22.0"
        return {
            "commits": [
                {"commit": {"message": "feat(api): add new sensor"}},
                {"commit": {"message": "fix: resolve timeout issue"}},
                {"commit": {"message": "chore: bump internal deps"}},
            ]
        }

    monkeypatch.setattr("bump_api_dependency._fetch_compare", _fetch_compare)

    commit_type, body = classify_release_notes(releases, "4.21.0")
    assert commit_type == "feat"
    assert "### Features" in body
    assert "- 4.22.0: add new sensor" in body
    assert "### Bug Fixes" in body
    assert "- 4.22.0: resolve timeout issue" in body
    assert "chore: bump internal deps" not in body


def test_classify_release_notes_empty_body_falls_back_to_ignored_commits(monkeypatch):
    releases = [{"tag_name": "v4.22.0", "body": "   "}]

    def _fetch_compare(_owner, _repo, base, head, _token):
        return {
            "commits": [
                {"commit": {"message": "chore: cleanup"}},
                {"commit": {"message": "docs: update readme"}},
                {"commit": {"message": "ci: tweak pipeline"}},
                {"commit": {"message": "test: add coverage"}},
            ]
        }

    monkeypatch.setattr("bump_api_dependency._fetch_compare", _fetch_compare)

    commit_type, body = classify_release_notes(releases, "4.21.0")
    assert commit_type == "chore"
    assert "### Other Changes" in body
    assert "- 4.22.0: cleanup" in body
    assert "- 4.22.0: update readme" in body


def test_update_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": ["hyundai_kia_connect_api==4.21.0"]})
    )
    update_manifest(str(manifest), "4.23.0")
    data = json.loads(manifest.read_text())
    assert data["requirements"] == ["hyundai_kia_connect_api==4.23.0"]


@pytest.fixture
def fake_releases(monkeypatch):
    def _fetch(_owner, _repo, _token):
        return [
            {
                "tag_name": "v4.22.0",
                "body": "### Features\n- new sensor\n",
            }
        ]

    monkeypatch.setattr(
        "bump_api_dependency._fetch_releases",
        _fetch,
    )


def test_main_noop_does_not_change_manifest(
    tmp_path, monkeypatch, fake_releases, capsys
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": ["hyundai_kia_connect_api==4.21.0"]})
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["bump_api_dependency.py", str(manifest), "--noop"],
    )

    assert main() == 0

    data = json.loads(manifest.read_text())
    assert data["requirements"] == ["hyundai_kia_connect_api==4.21.0"]

    captured = capsys.readouterr()
    # A bump is available, so the workflow signal is "noop": false; --noop only
    # prevents writing the manifest.
    assert '"noop": false' in captured.out


def test_main_without_noop_changes_manifest(tmp_path, monkeypatch, fake_releases):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": ["hyundai_kia_connect_api==4.21.0"]})
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["bump_api_dependency.py", str(manifest)],
    )

    assert main() == 0

    data = json.loads(manifest.read_text())
    assert data["requirements"] == ["hyundai_kia_connect_api==4.22.0"]


def test_main_at_latest_is_noop(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": ["hyundai_kia_connect_api==4.22.0"]})
    )

    def _no_new_releases(_owner, _repo, _token):
        return []

    monkeypatch.setattr("bump_api_dependency._fetch_releases", _no_new_releases)
    monkeypatch.setattr(
        sys,
        "argv",
        ["bump_api_dependency.py", str(manifest)],
    )

    assert main() == 0

    data = json.loads(manifest.read_text())
    assert data["requirements"] == ["hyundai_kia_connect_api==4.22.0"]

    captured = capsys.readouterr()
    assert '"noop": true' in captured.out
    assert "already at latest version" in captured.out
