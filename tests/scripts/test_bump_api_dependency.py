import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from bump_api_dependency import get_current_pin, classify_release_notes, update_manifest


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
    commit_type, body = classify_release_notes(releases)
    assert commit_type == "feat"
    assert "### Features" in body
    assert "- 4.22.0:" in body
    assert "### Bug Fixes" in body
    assert "- 4.23.0:" in body


def test_update_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"requirements": ["hyundai_kia_connect_api==4.21.0"]})
    )
    update_manifest(str(manifest), "4.23.0")
    data = json.loads(manifest.read_text())
    assert data["requirements"] == ["hyundai_kia_connect_api==4.23.0"]
