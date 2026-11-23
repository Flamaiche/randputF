from pathlib import Path

import tools.check_anchors as check_anchors


def test_resolve_target_accepte_un_lien_sans_ancre(tmp_path: Path):
    doc = tmp_path / "docs" / "page.md"
    target = tmp_path / "README.md"

    resolved, anchor = check_anchors.resolve_target(doc, "../README.md")

    assert resolved == target
    assert anchor == ""


def test_lien_relatif_sans_ancre_existant_passe(tmp_path: Path):
    doc = tmp_path / "docs" / "page.md"
    doc.parent.mkdir(parents=True)
    other = doc.parent / "autre.md"
    other.write_text("# Autre\n", encoding="utf-8")
    doc.write_text("[autre](autre.md)\n", encoding="utf-8")

    assert check_anchors.main([str(doc)]) == 0


def test_lien_relatif_sans_ancre_casse_est_signale(tmp_path: Path, capsys):
    doc = tmp_path / "docs" / "page.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("[absent](absent.md)\n", encoding="utf-8")

    assert check_anchors.main([str(doc)]) == 1
    assert "cible introuvable" in capsys.readouterr().err
