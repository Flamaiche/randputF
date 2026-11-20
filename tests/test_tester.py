"""Tests du testeur de dump : contrôle, rejeu et trois pages HTML."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from tool import tester
from tool.audit.fields import CONSUMED, COSMETIC, PARTIAL, classify_dump_fields
from tool.exporters.mod_seed import build_vanilla_seed
from tool.exporters.report import write_full_report
from tool.parsers.vanilla import load_db_from_dump
from tool.tester import CheckReport, check_state, run_dump_test
from tool.validator.solver import validate_seed


def test_check_state_joue_le_dump_memme_avec_des_problemes(monkeypatch):
    monkeypatch.setattr(tester, "validate_seed", lambda state: ["cycle"])
    monkeypatch.setattr(
        tester,
        "play",
        lambda db, state: SimpleNamespace(
            victory=False,
            blocker="tech:cost",
            researched=3,
            total_techs=9,
        ),
    )
    check = check_state(SimpleNamespace(), {"meta": {"origin": "dump"}})
    assert check == CheckReport(
        issues=["cycle"],
        victory=False,
        blocker="tech:cost",
        researched=3,
        total_techs=9,
    )
    assert not check.ok


def test_run_dump_test_ecrit_les_trois_vues_sans_generer(monkeypatch, tmp_path):
    captured = {}
    state = {
        "meta": {"origin": "dump"},
        "recipes": [],
        "technologies": [{"id": "tech-a"}],
    }
    monkeypatch.setattr(tester, "build_vanilla_seed", lambda dump: state)
    monkeypatch.setattr(
        tester,
        "check_state",
        lambda db, tested: CheckReport(victory=True),
    )
    def fake_dump_html(dump, path):
        Path(path).write_text("dump", encoding="utf-8")
        return Path(path)

    monkeypatch.setattr(tester, "write_dump_html", fake_dump_html)
    monkeypatch.setattr(
        tester,
        "write_seed_graph_html",
        lambda tested, path: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, ["dot"])
        ),
    )

    def fake_report(seed, path, db, **kwargs):
        captured.update(kwargs)
        Path(path).write_text("rapport", encoding="utf-8")
        return {"path": Path(path)}

    monkeypatch.setattr(tester, "write_full_report", fake_report)
    monkeypatch.setattr(
        tester,
        "compute_difficulty",
        lambda seed: SimpleNamespace(total=12.5),
    )

    result = run_dump_test(SimpleNamespace(), {"meta": {}}, tmp_path, source="vanilla")
    assert result.dump_html.name == "vanilla.dump.html"
    assert result.graph_html is not None
    assert result.graph_html.name == "vanilla.graph.html"
    assert result.report_html.name == "vanilla.report.html"
    assert "vue textuelle" in result.graph_html.read_text(encoding="utf-8")
    assert result.difficulty_total == 12.5
    assert result.check.ok
    assert captured["checks"]["ok"] is True
    assert captured["mod_label"] == "état testé"
    assert captured["vanilla_label"] == "dump"


def test_classification_des_champs_presents():
    dump = {
        "items": {"ae-item": {"fuel_value": 8, "order": "a"}},
        "technologies": {"ae-tech": {"research_unit_count_formula": "level"}},
    }

    audit = classify_dump_fields(dump)
    states = {
        (field["section"], field["field"]): field["status"]
        for field in audit["fields"]
    }

    assert states[("items", "fuel_value")] == CONSUMED
    assert states[("items", "order")] == COSMETIC
    assert states[("technologies", "research_unit_count_formula")] == PARTIAL
    assert audit["counts"][CONSUMED] == 1
    assert audit["counts"][COSMETIC] == 1
    assert audit["counts"][PARTIAL] == 1


def test_rapport_leger_inclut_la_couverture_du_dump(tmp_path):
    seed = {"meta": {}, "pools": {}, "technologies": [], "recipes": [{}] * 2001}
    dump = {"items": {"ae-item": {"fuel_value": 8, "order": "a"}}}

    result = write_full_report(seed, tmp_path / "rapport.html", dump=dump, lightweight=True)
    document = (tmp_path / "rapport.html").read_text(encoding="utf-8")

    assert "id='couverture-dump'" in document
    assert "fuel_value" in document
    assert result["coverage"]["counts"][CONSUMED] == 1


def test_progressivite_dump_independante_de_l_ordre():
    seed = {
        "meta": {"origin": "dump"},
        "pools": {"raw_resources": ["minerai"]},
        "recipes": [
            {
                "name": "coffre",
                "ingredients": [{"name": "plaque"}],
                "results": [{"name": "coffre"}],
            },
            {
                "name": "plaque",
                "ingredients": [{"name": "minerai"}],
                "results": [{"name": "plaque"}],
            },
        ],
    }
    assert validate_seed(seed) == []


def test_dump_vanilla_passe_controle_et_rejeu():
    dump = json.loads(
        (Path(__file__).parent.parent / "data" / "vanilla_dump.json").read_text(
            encoding="utf-8"
        )
    )
    db = load_db_from_dump(dump)
    state = build_vanilla_seed(dump)

    check = check_state(db, state)

    assert check.issues == []
    assert check.victory is True
    assert check.researched == check.total_techs
