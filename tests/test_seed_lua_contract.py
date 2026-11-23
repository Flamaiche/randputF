from pathlib import Path

from tool.exporters.mod_seed import LUA_HEADER, _to_lua, write_seed_files


def test_to_lua_echappe_les_chaines_et_lescles():
    lua = _to_lua({"clé": 'a"b\\c\n', "list": [1, True, None]})

    assert '["clé"] = "a\\"b\\\\c\\n"' in lua
    assert "    true," in lua
    assert "    nil," in lua


def test_write_seed_files_produit_un_lua_chargeable(tmp_path: Path):
    seed = {
        "pools": {"raw_resources": []},
        "recipes": [],
        "technologies": [],
        "meta": {},
        "note": 'ligne\navec "guillemets"',
    }
    out = tmp_path / "seed"

    write_seed_files(seed, out)

    lua = (out / "seed.lua").read_text(encoding="utf-8")
    assert lua.startswith(LUA_HEADER)
    assert lua.startswith(LUA_HEADER + "return {")
    assert 'note = "ligne\\navec \\"guillemets\\""' in lua
    assert '"total"' in (out / "seed.json").read_text(encoding="utf-8")
