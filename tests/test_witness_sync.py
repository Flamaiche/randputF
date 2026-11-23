from pathlib import Path

from tools.sync_witness import FILES, current_hash, sync_files, sync_text


def test_current_hash_lit_la_ci(tmp_path: Path):
    ci = tmp_path / ".github" / "workflows" / "ci.yml"
    ci.parent.mkdir(parents=True)
    ci.write_text(
        "jobs:\n  run: randputf witness --seed 5 --expect " + "a" * 32 + "\n",
        encoding="utf-8",
    )

    assert current_hash(tmp_path) == "a" * 32


def test_sync_text_remplace_seulement_le_temoin_courant():
    old = "a" * 32
    new = "b" * 32
    historic = "c" * 32
    text = f"témoin courant {old}, historique {historic}"

    assert sync_text(text, old, new) == f"témoin courant {new}, historique {historic}"


def test_sync_files_ecrit_les_fichiers_concernes(tmp_path: Path):
    old = "a" * 32
    new = "b" * 32
    for rel in FILES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"témoin {old}\n", encoding="utf-8")

    changed = sync_files(tmp_path, old, new)

    assert changed == list(FILES)
    for rel in FILES:
        assert (tmp_path / rel).read_text(encoding="utf-8") == f"témoin {new}\n"
