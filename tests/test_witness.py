"""Témoin de déterminisme : la méthode de mesure est reproductible à l'octet.

Régression du bug réel : ``sorted(os.walk(dir))`` triait les tuples APRÈS le
parcours — l'ordre d'émission suivait ``os.scandir`` et variait selon la
machine (locale/en vs locale/fr). Ces tests verrouillent le tri par chemin
relatif canonique, indépendant du système de fichiers.
"""

from pathlib import Path

from tool.common.witness import canonical_entries, witness_md5


def _make_mod_dir(tmp_path: Path, order: list[str]) -> Path:
    d = tmp_path / "randputF_1.0.0"
    content = {
        "info.json": b'{"name": "randputF", "version": "1.0.0"}',
        "data.lua": b"-- data",
        "locale/en/randputf.cfg": b"[en]",
        "locale/fr/randputf.cfg": b"[fr]",
        "seed/seed.json": b"{}",
        "seed.graph.html": b"<svg version Graphviz>",
    }
    for key in order:
        path = d / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content[key])
    return d


def test_ordre_d_insertion_en_fr_no_change_le_md5(tmp_path):
    """Le bug réel vu en prod : locale/en et locale/fr lus dans un ordre qui
    varie selon la machine. Le md5 ne doit PAS dépendre de cet ordre."""
    repo_order = _make_mod_dir(tmp_path / "a", ["locale/en/randputf.cfg", "locale/fr/randputf.cfg"])
    wheel_order = _make_mod_dir(tmp_path / "b", ["locale/fr/randputf.cfg", "locale/en/randputf.cfg"])

    assert witness_md5(repo_order) == witness_md5(wheel_order)


def test_entrees_triees_par_chemin_relatif_canonique(tmp_path):
    d = _make_mod_dir(tmp_path, ["locale/fr/randputf.cfg", "locale/en/randputf.cfg"])
    rels = [rel for rel, _ in canonical_entries(d)]
    assert rels == sorted(rels)
    assert all("/" in rel for rel in rels)  # séparateur canonique, pas os.sep


def test_seed_graph_html_exclu_du_temoin(tmp_path):
    d = _make_mod_dir(tmp_path, ["seed.graph.html"])
    rels = [rel for rel, _ in canonical_entries(d)]
    assert "seed.graph.html" not in rels


def test_witness_reproductible_sur_deux_assemblages(tmp_path):
    """Wheel et dépôt doivent produire le même digest pour la même seed."""
    from tool.generator.pipeline import generate_seed
    from tool.exporters.mod_seed import write_seed_files
    from tool.parsers.vanilla import load_db_from_dump
    import json

    db = load_db_from_dump(
        json.loads((Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json").read_text(encoding="utf-8"))
    )
    db.seed_value = 5
    seed = generate_seed(db, validate=False)

    digests = []
    for build in range(2):
        dirname = tmp_path / f"b{build}" / "randputF_1.0.0"
        dirname.mkdir(parents=True)
        write_seed_files(seed, dirname / "seed")
        (dirname / "info.json").write_text('{"name": "randputF", "version": "1.0.0"}')
        (dirname / "control.lua").write_text("-- control")
        (dirname / "seed.graph.html").write_text("<svg>")
        digests.append(witness_md5(dirname))

    assert digests[0] == digests[1]


def test_witness_independant_du_nom_du_dossier(tmp_path):
    """Le préfixe racine est MOD_NAME_VERSIONED, PAS mod_dir.name : deux
    dossiers nommés différemment mais avec le même contenu doivent donner le
    même digest. (Point relevé en review : mod_dir.name fuitait dans le md5.)"""
    src = _make_mod_dir(tmp_path / "src", ["locale/fr/randputf.cfg", "locale/en/randputf.cfg"])
    renamed_dir = _make_mod_dir(tmp_path / "copie", ["locale/fr/randputf.cfg", "locale/en/randputf.cfg"])
    renamed = renamed_dir.with_name("mon_dossier_renomme")
    renamed_dir.rename(renamed)

    assert src.name != renamed.name
    assert witness_md5(src) == witness_md5(renamed)
    # et la racine est bien randputF_<version>, quel que soit le dossier
    ref = witness_md5(src)
    assert ref == witness_md5(renamed, prefix="randputF_1.0.0")