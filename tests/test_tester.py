"""Tests du testeur de dump : contrôle, rejeu et trois pages HTML."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tool import tester
from tool.audit.fields import CONSUMED, COSMETIC, PARTIAL, classify_dump_fields
from tool.exporters.mod_seed import build_vanilla_seed
from tool.exporters.report import write_full_report
from tool.parsers.vanilla import load_db_from_dump
from tool.tester import CheckReport, Progress, check_state, run_dump_test
from tool.validator.solver import validate_seed


class ProgressRecorder:
    def __init__(self, stage: str | None = None):
        self.stage = stage
        self.percent = 0
        self.events = []
        self.source = None

    def enter(self, stage: str, detail: str = "") -> None:
        self.stage = stage
        self.percent = 0
        self.events.append(("enter", stage, detail))

    def update(self, percent: int, detail: str | None = None) -> None:
        self.percent = percent
        self.events.append(("update", self.stage, percent, detail))

    def watch(self, source=None) -> None:
        self.source = source

    def finish(self, detail: str = "terminé") -> None:
        self.percent = 100
        self.events.append(("finish", self.stage, detail))


def test_check_state_joue_le_dump_memme_avec_des_problemes(monkeypatch):
    monkeypatch.setattr(
        tester, "validate_seed", lambda state, on_progress=None: ["cycle"]
    )
    monkeypatch.setattr(
        tester,
        "play",
        lambda db, state, on_progress=None: SimpleNamespace(
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


def test_progress_affiche_un_pourcentage_par_etape():
    stream = io.StringIO()
    progress = Progress(stream, enabled=True, refresh=0)

    progress.start()
    progress.enter("acquisition")
    progress.update(50, "dump lu")
    progress.enter("controle")
    progress.update(25, "validation en cours")
    progress.finish()

    output = stream.getvalue()
    assert "Acquisition du dump [" in output
    assert " 50% 1/5" in output
    assert "Contrôle de l'état [" in output
    assert " 25% 2/5" in output
    assert "100%" in output
    assert "fin étape" in output


def test_progress_relit_les_infos_a_chaque_affichage():
    stream = io.StringIO()
    progress = Progress(stream, enabled=True, refresh=0)
    infos = {"percent": 10, "detail": "première lecture"}
    progress.enter("rejeu")
    progress.watch(lambda: (infos["percent"], infos["detail"]))

    infos["percent"] = 75
    infos["detail"] = "lecture suivante"
    progress.update(0)
    progress.update(0)

    output = stream.getvalue()
    assert output.count(" 75% 3/5 — lecture suivante") == 1
    assert "première lecture" not in output


def test_progress_ne_fait_pas_grandir_leta_quand_le_pourcentage_est_fige(monkeypatch):
    stream = io.StringIO()
    now = [1000.0]
    monkeypatch.setattr(tester.time, "monotonic", lambda: now[0])
    progress = Progress(stream, enabled=True, refresh=0)

    progress.start()
    progress.enter("mesure")
    now[0] = 1001.0
    progress.update(10, "dépliage · 1 étape")
    first = stream.getvalue().splitlines()[-1]

    now[0] = 1100.0
    progress.update(10, "dépliage · 2 étapes")
    second = stream.getvalue().splitlines()[-1]

    assert "fin étape ~9s" in first
    assert "fin étape —" in second
    assert "fin étape ~891s" not in second


def test_progress_desactivee_necrit_rien():
    stream = io.StringIO()
    progress = Progress(stream, enabled=False, refresh=0)

    progress.start()
    progress.enter("controle")
    progress.finish()

    assert stream.getvalue() == ""


def test_check_state_pilote_controle_puis_rejeu(monkeypatch):
    progress = ProgressRecorder()

    def fake_validate(state, on_progress=None):
        if on_progress is not None:
            on_progress(50)
        return []

    def fake_play(db, state, on_progress=None):
        if on_progress is not None:
            on_progress(75, 3, 4)
        return SimpleNamespace(
            victory=True,
            blocker=None,
            researched=3,
            total_techs=4,
        )

    monkeypatch.setattr(tester, "validate_seed", fake_validate)
    monkeypatch.setattr(tester, "play", fake_play)

    check = check_state(SimpleNamespace(), {}, progress)

    assert check.ok
    assert [event[1] for event in progress.events if event[0] == "enter"] == [
        "controle",
        "rejeu",
    ]
    assert ("update", "controle", 50, "validation des invariants") in progress.events
    assert ("update", "rejeu", 75, "partie simulée · 3/4 techs") in progress.events


@pytest.mark.parametrize(
    ("out_name", "folder"),
    [(None, "vanilla"), ("randputF_0.0.1", "randputF_0.0.1")],
)
def test_run_dump_test_ecrit_les_trois_vues_sans_generer(
    monkeypatch, tmp_path, out_name, folder
):
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
        lambda db, tested, progress=None: CheckReport(victory=True),
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
        kwargs["on_progress"](25, "série de difficulté")
        Path(path).write_text("rapport", encoding="utf-8")
        return {"path": Path(path), "difficulty_total": 42.0}

    monkeypatch.setattr(tester, "write_full_report", fake_report)

    def interdit(seed, on_progress=None):
        raise AssertionError("difficulté recalculée alors que le rapport la fournit")

    monkeypatch.setattr(tester, "compute_difficulty", interdit)

    progress = ProgressRecorder("acquisition")
    kwargs = {} if out_name is None else {"out_name": out_name}
    result = run_dump_test(
        SimpleNamespace(),
        {"meta": {}},
        tmp_path,
        source="vanilla",
        progress=progress,
        **kwargs,
    )
    assert [event[1] for event in progress.events if event[0] == "enter"] == [
        "mesure",
        "rapport",
    ]
    assert ("update", "acquisition", 100, "normalisation terminée") in progress.events
    assert ("update", "mesure", 25, "série de difficulté") in progress.events
    assert ("update", "mesure", 96, "rapport complet écrit") in progress.events
    assert ("update", "rapport", 50, "navigateur écrit") in progress.events
    assert progress.events[-1] == ("finish", "rapport", "vues HTML écrites")
    assert result.dump_html == tmp_path / folder / "vanilla.dump.html"
    assert result.graph_html is not None
    assert result.graph_html == tmp_path / folder / "vanilla.graph.html"
    assert result.report_html == tmp_path / folder / "vanilla.report.html"
    assert "vue textuelle" in result.graph_html.read_text(encoding="utf-8")
    assert result.difficulty_total == 42.0
    assert result.check.ok
    assert captured["checks"]["ok"] is True
    assert captured["mod_label"] == "état testé"
    assert captured["vanilla_label"] == "dump"


def test_run_dump_test_fragmentle_calcul_de_difficulté(monkeypatch, tmp_path):
    state = {"meta": {"origin": "dump"}, "recipes": [], "technologies": []}
    monkeypatch.setattr(tester, "build_vanilla_seed", lambda dump: state)
    monkeypatch.setattr(
        tester,
        "check_state",
        lambda db, tested, progress=None: CheckReport(victory=True),
    )
    monkeypatch.setattr(
        tester,
        "write_dump_html",
        lambda dump, path: Path(path).write_text("dump", encoding="utf-8") or Path(path),
    )
    monkeypatch.setattr(
        tester,
        "write_seed_graph_html",
        lambda tested, path: Path(path).write_text("graphe", encoding="utf-8"),
    )

    def fake_report(seed, path, db, **kwargs):
        Path(path).write_text("rapport", encoding="utf-8")
        return {"path": Path(path)}

    def fake_compute(seed, on_progress=None):
        assert on_progress is not None
        on_progress(40)
        return SimpleNamespace(total=8.0)

    monkeypatch.setattr(tester, "write_full_report", fake_report)
    monkeypatch.setattr(tester, "compute_difficulty", fake_compute)

    progress = ProgressRecorder("acquisition")
    result = run_dump_test(
        SimpleNamespace(), {"meta": {}}, tmp_path, source="vanilla", progress=progress
    )

    assert ("update", "mesure", 97, "difficulté calculée") in progress.events
    assert result.difficulty_total == 8.0


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
    assert "id='difficulte'" in document
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


def test_progressivite_dump_cycle_positif_avec_starter_externe():
    seed = {
        "meta": {"origin": "dump"},
        "pools": {"raw_resources": ["starter", "catalyseur"]},
        "recipes": [
            {
                "name": "faire-a",
                "ingredients": [
                    {"name": "b", "amount": 1},
                    {"name": "starter", "amount": 1},
                ],
                "results": [{"name": "a", "amount": 8}],
            },
            {
                "name": "faire-b",
                "ingredients": [
                    {"name": "a", "amount": 1},
                    {"name": "catalyseur", "amount": 1},
                ],
                "results": [{"name": "b", "amount": 50}],
            },
        ],
    }

    assert validate_seed(seed) == []


def test_progressivite_dump_cycle_equilibre_avec_conteneur():
    seed = {
        "meta": {"origin": "dump"},
        "pools": {"raw_resources": ["conteneur"]},
        "recipes": [
            {
                "name": "remplir",
                "ingredients": [
                    {"name": "fluide", "amount": 50},
                    {"name": "conteneur", "amount": 1},
                ],
                "results": [{"name": "conteneur-fluide", "amount": 1}],
            },
            {
                "name": "vider",
                "ingredients": [{"name": "conteneur-fluide", "amount": 1}],
                "results": [
                    {"name": "fluide", "amount": 50},
                    {"name": "conteneur", "amount": 1},
                ],
            },
        ],
    }

    assert validate_seed(seed) == []


def test_progressivite_dump_residu_combustion_et_lancement():
    seed = {
        "meta": {"origin": "dump"},
        "pools": {"raw_resources": ["minerai"]},
        "items": {
            "combustible": {"burnt_result": "cendre"},
            "lançable": {
                "rocket_launch_products": [{"name": "retour", "amount": 1}]
            },
        },
        "recipes": [
            {
                "name": "faire-combustible",
                "ingredients": [{"name": "minerai", "amount": 1}],
                "results": [{"name": "combustible", "amount": 1}],
            },
            {
                "name": "faire-lançable",
                "ingredients": [{"name": "minerai", "amount": 1}],
                "results": [{"name": "lançable", "amount": 1}],
            },
            {
                "name": "utiliser-cendre",
                "ingredients": [{"name": "cendre", "amount": 1}],
                "results": [{"name": "produit", "amount": 1}],
            },
            {
                "name": "utiliser-retour",
                "ingredients": [{"name": "retour", "amount": 1}],
                "results": [{"name": "produit", "amount": 1}],
            },
        ],
    }

    assert validate_seed(seed) == []


def test_progressivite_dump_fluide_de_procede():
    seed = {
        "meta": {"origin": "dump"},
        "pools": {
            "raw_resources": ["sel"],
            "process_fluids": ["fluide-procede"],
        },
        "recipes": [
            {
                "name": "chauffer",
                "ingredients": [
                    {"name": "fluide-procede", "amount": 100},
                    {"name": "sel", "amount": 1},
                ],
                "results": [{"name": "sel-chaud", "amount": 1}],
            }
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
