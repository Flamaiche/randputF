"""Vérifie le rendu HTML du rapport de partie simulée."""

import json
from pathlib import Path

import pytest

from tool.exporters.vanilla_complexity import write_playthrough_html

DUMP_PATH = Path(__file__).resolve().parents[1] / "data" / "vanilla_dump.json"


@pytest.fixture(scope="module")
def dump() -> dict:
    return json.loads(DUMP_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report(dump: dict, tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("report") / "playthrough.html"
    result = write_playthrough_html(dump, out)
    result["html"] = out.read_text(encoding="utf-8")
    return result


def test_lists_every_item_and_fluid(report: dict, dump: dict) -> None:
    names = {row["name"] for row in report["rows"]}
    expected = set(dump["items"]) | set(dump["fluids"])
    assert expected <= names


def test_every_row_has_a_tag(report: dict) -> None:
    assert all(row["tags"] != "—" for row in report["rows"])


def test_external_column_is_hidden_when_all_zero(report: dict) -> None:
    assert report["analysis"]["external_items"] == []
    assert "data-key='external'" not in report["html"]
    assert "data-key='tags'" in report["html"]


def test_space_science_row_reports_launch_crafts(report: dict) -> None:
    rows = {row["name"]: row for row in report["rows"]}
    assert rows["space-science-pack"]["crafts"] > 0
    assert rows["space-science-pack"]["external"] == 0
    assert "rocket-silo" in report["analysis"]["buildings"]


def test_item_tags_prefer_display_type() -> None:
    from tool.exporters.vanilla_complexity import _item_tags

    fake = {
        "items": {
            "space-science-pack": {
                "type": "tool",
                "display_type": "item",
                "subgroup": "science-pack",
            }
        },
        "fluids": {},
    }
    assert _item_tags("space-science-pack", fake) == "item / science-pack"


def test_cli_report_generates_html(tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "report.html"
    assert not out.exists()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tool",
            "report",
            "--dump",
            str(DUMP_PATH),
            "--out",
            str(out),
        ],
        cwd=DUMP_PATH.parents[1],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    assert "Rapport :" in proc.stdout
    assert "[OK] aucun item fourni en externe" in proc.stdout
