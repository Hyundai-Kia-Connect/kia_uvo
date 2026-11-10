import io
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from release_notes import api_changes, main, parse_bump_body

API = "https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api"

# Body as the squash merge stores it: long items wrapped across lines.
BUMP_511 = f"""fix(deps): bump hyundai_kia_connect_api 5.1.0 → 5.1.1 (#2086)

Bump `hyundai_kia_connect_api` from `5.1.0` to `5.1.1`.

Upstream versions included in this bump: 5.1.1.

### Bug Fixes
- 5.1.1: * **ca:** check errors in PIN validation
([Hyundai-Kia-Connect/hyundai_kia_connect_api#1565]({API}/issues/1565))
- 5.1.1: * **eu:** read cached status from the CCS2 endpoint for every
car

### Other Changes
- 5.1.1: No categorized release notes.

Co-authored-by: GitHub Action <action@github.com>"""

BUMP_512 = """feat(deps): bump hyundai_kia_connect_api 5.1.1 → 5.1.2 (#2088)

### Features
- 5.1.2: * **eu:** map DTE.ICE

### Bug Fixes
- 5.1.2: * **ca:** check errors in PIN validation
([Hyundai-Kia-Connect/hyundai_kia_connect_api#1565](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api/issues/1565))"""


def test_parse_bump_body_rejoins_wrapped_items():
    assert parse_bump_body(BUMP_511) == {
        "Bug Fixes": [
            (
                "**ca:** check errors in PIN validation "
                f"([Hyundai-Kia-Connect/hyundai_kia_connect_api#1565]({API}/issues/1565))"
            ),
            "**eu:** read cached status from the CCS2 endpoint for every car",
        ]
    }


def test_api_changes_merges_bumps_and_dedupes():
    notes = api_changes([BUMP_511, BUMP_512])
    assert notes.startswith("### hyundai_kia_connect_api 5.1.0 → 5.1.2\n")
    assert notes.index("#### Features") < notes.index("#### Bug Fixes")
    assert "* **eu:** map DTE.ICE" in notes
    assert notes.count("check errors in PIN validation") == 1
    assert "Other Changes" not in notes


def test_api_changes_empty():
    assert api_changes([]) == ""
    assert (
        api_changes(["chore(deps): bump hyundai_kia_connect_api 1.0.0 → 1.0.1"]) == ""
    )


def _init_repo(path: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        subprocess.run(cmd, cwd=path, check=True)


def _commit(message: str) -> None:
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", message], check=True)


def test_main_only_reads_bumps_since_last_stable_tag(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    _commit(BUMP_511)
    subprocess.run(["git", "tag", "v4.0.0"], check=True)
    _commit("fix(sensor): unrelated")
    _commit(BUMP_512)
    # A beta tag on HEAD must not move the range.
    subprocess.run(["git", "tag", "v4.0.1-beta.1"], check=True)

    monkeypatch.setattr(sys, "stdin", io.StringIO("## 4.0.1\n\n* base notes\n"))
    assert main() == 0
    out = capsys.readouterr().out
    assert out.startswith("## 4.0.1\n\n* base notes\n\n### hyundai_kia_connect_api")
    assert "5.1.1 → 5.1.2" in out
    assert "read cached status" not in out


@pytest.mark.parametrize("base", ["", "## 4.0.1\n"])
def test_main_without_bumps_keeps_notes(tmp_path, monkeypatch, capsys, base):
    monkeypatch.chdir(tmp_path)
    _init_repo(tmp_path)
    _commit("fix: x")
    monkeypatch.setattr(sys, "stdin", io.StringIO(base))
    main()
    assert capsys.readouterr().out == base.rstrip() + "\n"
