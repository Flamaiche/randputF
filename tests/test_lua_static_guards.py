import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LUA_FILES = sorted((ROOT / "mod").glob("*.lua"))
STRAYED_LINE_RE = re.compile(r"^\s*:(?!:)")


def test_lua_a_au_moins_quatre_fichiers():
    assert len(LUA_FILES) >= 4


def test_aucune_ligne_lua_commentee_mal():
    offenders = []
    for path in LUA_FILES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if STRAYED_LINE_RE.match(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []
