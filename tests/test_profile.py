from tool.audit.graph import analyze_graph
from tool.audit.profile import difficulty_profile
from tool.exporters.complexity_graph import analyze_complexity
from tool.exporters.profile import render_profile_html
from tool.exporters.report import write_full_report


def _seed(facteur: int = 1) -> dict:
    return {
        "meta": {},
        "pools": {"raw_resources": ["minerai"]},
        "progression_order": ["tech-1"],
        "technologies": [
            {
                "id": "tech-1",
                "unit": {
                    "count": facteur,
                    "ingredients": [{"name": "pack-science", "amount": 1}],
                }
            }
        ],
        "recipes": [
            {
                "name": "randputf-plaque",
                "ingredients": [{"name": "minerai", "amount": 2}],
                "results": [{"name": "plaque", "amount": 1}],
                "energy": 2,
                "crafted_in": "four",
            },
            {
                "name": "randputf-pack-science",
                "ingredients": [{"name": "plaque", "amount": 1}],
                "results": [{"name": "pack-science", "amount": 1}],
                "energy": 1,
                "crafted_in": "assembleur",
            },
        ],
    }


def test_profil_difficulte_normalise_contre_la_reference():
    reference = _seed()
    modde = _seed(3)

    profile = difficulty_profile(modde, baseline_seed=reference)

    volume = profile["axes"]["volume"]
    assert volume["raw_values"]["raw_units_log"] == 6
    assert volume["raw_values"]["crafts_log"] == 6
    assert volume["values"]["raw_units_log"] > 0.8
    assert volume["ratio"] > 1
    assert profile["axes"]["structure"]["ratio"] == 1
    assert profile["score"] > 1


def test_profil_difficulte_sans_reference_reste_lisible():
    profile = difficulty_profile(_seed())

    assert profile["score"] is None
    assert profile["axes"]["structure"]["ratio"] is None
    assert profile["axes"]["volume"]["raw_values"]["machine_seconds_log"] == 3


def test_rapport_inclut_le_profil_dans_le_sommaire(tmp_path):
    path = tmp_path / "rapport.html"

    result = write_full_report(_seed(), path, dump={}, lightweight=True)

    document = path.read_text(encoding="utf-8")
    assert "id='profil-difficulte'" in document
    assert "id='profil-difficulte-table'" in document
    assert 'href="#profil-difficulte"' in document
    assert 'href="#profil-difficulte-table"' in document
    assert result["difficulty_profile"] is not None


def test_rapport_ignore_le_profil_avec_difficulte(tmp_path):
    path = tmp_path / "rapport.html"

    result = write_full_report(
        _seed(),
        path,
        dump={},
        skip=frozenset({"complexity", "difficulty", "playthrough"}),
    )

    document = path.read_text(encoding="utf-8")
    assert "id='profil-difficulte'" not in document
    assert 'href="#profil-difficulte"' not in document
    assert 'href="#difficulte"' not in document
    assert result["difficulty_profile"] is None


def test_progression_rapport_leger_est_monotone(tmp_path):
    progression: list[int] = []

    write_full_report(
        _seed(),
        tmp_path / "rapport.html",
        dump={},
        lightweight=True,
        on_progress=lambda percent, _detail: progression.append(percent),
    )

    assert progression
    assert progression == sorted(progression)


def test_un_seul_graphe_alimente_complexite_et_profil():
    seed = _seed(3)
    graph = analyze_graph(seed)

    complexity = analyze_complexity(seed, graph=graph)
    profile = difficulty_profile(seed, graph=graph)

    assert complexity["total_raw"] == 6
    assert profile["axes"]["volume"]["raw_values"]["raw_units_log"] == 6
    assert complexity["total_raw"] == profile["axes"]["volume"]["raw_values"]["raw_units_log"]


def test_profil_html_marque_le_ratio_sur_la_valeur():
    document = render_profile_html(difficulty_profile(_seed(3), baseline_seed=_seed()))

    assert "profile-note profile-ratio" in document
    assert "vanilla" in document
    assert "Indice global pondéré" in document


def test_rapport_inclut_les_ratios_de_complexite(tmp_path):
    path = tmp_path / "rapport.html"
    write_full_report(
        _seed(3),
        path,
        dump={},
        vanilla_seed=_seed(),
        skip=frozenset({"playthrough"}),
    )

    document = path.read_text(encoding="utf-8")
    assert "Les « ×N » comparent chaque valeur à vanilla" in document
    assert "×3 vanilla" in document
