from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "mod" / "locale"


def _keys(path: Path) -> dict[tuple[str, str], str]:
    keys: dict[tuple[str, str], str] = {}
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            keys[(section, key.strip())] = value
    return keys


def test_locales_en_fr_ont_les_memes_cles():
    en = _keys(LOCALES / "en" / "randputf.cfg")
    fr = _keys(LOCALES / "fr" / "randputf.cfg")

    assert set(en) == set(fr)
    for key in en:
        assert en[key].count("%s") == fr[key].count("%s")


def test_cle_randputf_requises_presentes():
    keys = {key for _, key in _keys(LOCALES / "en" / "randputf.cfg")}
    required = {
        "offshore-pump-name",
        "offshore-pump-description",
        "phantom-lake-name",
        "generator-any-fluid-description",
        "boiler-any-fluid-description",
        "assigned-fluid-in-description",
        "assigned-fluid-in-out-description",
    }

    assert required <= keys
