from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
DOCS = (
    "CHANGELOG.md",
    "docs/DEVIANCES.md",
    "docs/graphe-interactif.md",
    "docs/release.md",
    "notes/v0.0.2.md",
)


def test_workflow_zippe_le_dossier_genere():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'randputf generate --seed 5 --out /tmp/modrel' in text
    assert 'cd /tmp/modrel && zip -qr "/tmp/randputF_${VERSION}.zip" "randputF_${VERSION}"' in text
    assert "/tmp/modrel/mods/" not in text


def test_docs_decrivent_le_chemin_reel_du_zip():
    for rel in DOCS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "/tmp/modrel/mods/" not in text, rel
        assert "source à aligner" not in text, rel
