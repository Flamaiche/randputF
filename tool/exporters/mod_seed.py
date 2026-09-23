"""Export de la seed vers le dossier du mod.

Ecrit deux fichiers :
- seed.json : source de vérité (validation, partage, debug) ;
- seed.lua  : miroir généré (return {...}) que data.lua charge nativement,
  evitant tout parseur JSON en data-stage.

Structure seed :
{
  meta: {seed, generator_version, factorio_version},
  pools: {item_resources: [...], fluid_resources: [...],
          vehicle_weapons: [<items gun de la pool montée §7>],
          vehicle_range_scaling: {base_size, scale}},
  map:   {patches: [{kind, resource, richness,
                     center:{x,y}, count, well_seed, cluster_radius  -- gisement §6.5 (item ET fluide)
                    }],
          lakes: [{resource, richness}]}, -- lacs de fluide §7.5
  starter_kit: [{type, name, count}],
  free_researches: [...],
  recipes: [{name, ingredients:[{type,name,amount,produced_by?}],
             results:[{type,name,amount}], crafted_in?, category?,
             on_the_spot_unlock?}],
  technologies: [{id, localised_name, prerequisites, unit{count,ingredients},
                  effects}],
  progression_order: [...],
  vehicle_armament: {<véhicule>: [<items gun assignés §7>]} -- pool cachée :
                 ne sert QU'à l'assignation ; le mod CLONE chaque arme pour
                 le véhicule (jamais craftée).
  building_fluid_assignments: {<bâtiment>: {input: <fluide>, output?: <fluide>}}
                 -- §6/§10 : fluides assignés aux bâtiments à comportement fixe
                 (turbines, boilers). Le mod applique les filters et tooltips.
}
"""

from __future__ import annotations

import json
from pathlib import Path

from tool.audit.difficulty import compute_difficulty

LUA_HEADER = "-- Généré par randputF tool. Ne pas éditer à la main.\n"


def write_seed_files(seed: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Difficulté injectée à l'export (jamais dans le pipeline) : le mod
    # l'affiche en chat au spawn. ``difficulty`` = total de l'ardoise.
    exported = dict(seed)
    total = compute_difficulty(seed).total
    exported["difficulty"] = {
        "total": total,
        "total_k": int(round(total / 1000)),
    }
    (out_dir / "seed.json").write_text(
        json.dumps(exported, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "seed.lua").write_text(
        LUA_HEADER + "return " + _to_lua(exported) + "\n", encoding="utf-8"
    )
    locale_en = out_dir.parent / "locale" / "en"
    locale_fr = out_dir.parent / "locale" / "fr"
    for locale_dir in (locale_en, locale_fr):
        if locale_dir.exists():
            locale_dir.mkdir(parents=True, exist_ok=True)
            (locale_dir / "seed.cfg").write_text(
                _locale_cfg(exported), encoding="utf-8"
            )


def _locale_cfg(seed: dict) -> str:
    """[autoplace-control-names] pour chaque patch (alias index -> resource) et
    chaque lac (§7.5, contrôle `randputf-lac-ctl-N` -> fluide)."""
    lines = ["[autoplace-control-names]"]
    seen = {}
    index = 0
    for patch in (seed.get("map") or {}).get("patches") or []:
        resource = patch.get("resource", "")
        if resource in seen:
            continue
        seen[resource] = True
        index += 1
        lines.append(f"randputf-ctl-{index}={resource}")
    for i, lake in enumerate((seed.get("map") or {}).get("lakes") or [], start=1):
        lines.append(f"randputf-lac-ctl-{i}={lake.get('resource', '')}")
    return "\n".join(lines) + "\n"


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
