"""Export de la seed vers le dossier du mod.

Ecrit deux fichiers :
- seed.json : source de vérité (validation, partage, debug) ;
- seed.lua  : miroir généré (return {...}) que data.lua charge nativement,
  evitant tout parseur JSON en data-stage.

Structure seed :
{
  meta: {seed, generator_version, factorio_version},
  pools: {item_resources: [...], fluid_resources: [...]},
  map:   {patches: [{kind, resource, richness}]},
  starter_kit: [{type, name, count}],
  free_researches: [...],
  recipes: [{name, ingredients:[{type,name,amount,produced_by?}],
             results:[{type,name,amount}], crafted_in?, category?,
             on_the_spot_unlock?}],
  technologies: [{id, localised_name, prerequisites, unit{count,ingredients},
                  effects}],
  progression_order: [...]
}
"""

from __future__ import annotations

import json
from pathlib import Path

LUA_HEADER = "-- Généré par randputF tool. Ne pas éditer à la main.\n"


def write_seed_files(seed: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seed.json").write_text(
        json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "seed.lua").write_text(
        LUA_HEADER + "return " + _to_lua(seed) + "\n", encoding="utf-8"
    )


def _to_lua(value, indent: int = 0) -> str:
    pad = "  " * indent
    child_pad = "  " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            lua_key = _lua_key(key)
            lines.append(f"{child_pad}{lua_key} = {_to_lua(item, indent + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, (list, tuple)):
        if not value:
            return "{}"
        lines = ["{"]
        for item in value:
            lines.append(f"{child_pad}{_to_lua(item, indent + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "nil"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _lua_key(key: str) -> str:
    if key.isidentifier() and key.isascii() and not key[0].isdigit():
        return key
    return f'["{key}"]'
