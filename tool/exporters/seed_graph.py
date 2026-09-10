"""Export du graphe de production d'une seed — IDEES C9.

Une seule sortie accompagne ``seed/seed.json`` lors de l'export ``--out``
(jamais dans ``mod/`` installé) :

- ``seed.graph.html`` : **version interactive** autonome — SVG du graphe,
  icônes embarquées en data-URI, zoom/pan à la souris et fiche au
  clic (nom, icône agrandie, ingrédients) pour chaque nœud.

Un nœud par item/fluide, une arête par dépendance de craft (produit →
ingrédient) étiquetée par la QUANTITÉ nécessaire au craft (`amount`).
L'icône de chaque nœud est celle que le jeu affiche réellement : fichier
exact ``<name>.png``, fluide ``fluid/<name>.png``, sinon icône déclarée
dans les prototypes installés (``raw-fish``→``fish.png``, ``stone-wall``→
``wall.png``…), sinon fût vide pour les ``*-barrel``. Les variantes de
stades (``-1/-2/-3``) et les icônes ``technology/`` sont exclues.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
from pathlib import Path

from tool.common.db import ENVIRONMENTAL_ITEMS
from tool.common.png_icon import crop_mip

DOT_HEADER = """// randputF seed {seed} - graphe de production (IDEES C9)
digraph seed {{
  bgcolor="#141419";
  rankdir=LR;
  concentrate=true;
  splines=spline;
  overlap=false;
  nodesep=0.7;
  ranksep=0.75;
  node [fontsize=11];
  edge [fontsize=8, arrowsize=.45];
"""


def _find_icons_dir() -> Path | None:
    """Répertoire des icônes vanilla de Factorio (data/base/graphics/icons),
    cherché dans les emplacements d'installation courants. None si absent."""
    home = Path.home()
    candidates = [
        Path("/var/home/hrichard/.steam/steam/steamapps/common/Factorio/data/base/graphics/icons"),
        Path("/var/run/host/.steam/steam/steamapps/common/Factorio/data/base/graphics/icons"),
        home / ".steam/steam/steamapps/common/Factorio/data/base/graphics/icons",
        home / ".local/share/Steam/steamapps/common/Factorio/data/base/graphics/icons",
        home / "Steam/steamapps/common/Factorio/data/base/graphics/icons",
        home / "Games/Factorio/data/base/graphics/icons",
        home / ".factorio/data/base/graphics/icons",
    ]
    for cand in candidates:
        if (cand / "iron-plate.png").is_file():
            return cand
    return None


_ICONS_DIR: Path | None = None


def _icons_dir() -> Path | None:
    global _ICONS_DIR
    if _ICONS_DIR is None:
        _ICONS_DIR = _find_icons_dir()
    return _ICONS_DIR


def _icon_path(name: str) -> Path | None:
    """Icône vanilla de ``name`` (item ou fluide) ou raccourci introuvable.

    Priorité : icône item exacte (`<name>.png`), puis fluide
    (`fluid/<name>.png`), puis l'icône déclarée dans les prototypes du jeu
    installé (cas où le fichier porte un autre nom : `raw-fish`→`fish.png`,
    `stone-wall`→`wall.png`, `burner-generator`→`steam-engine.png`…), puis un
    fût vide pour les `*-barrel` générés à la volée."""
    icons = _icons_dir()
    if icons is None:
        return None
    item = icons / f"{name}.png"
    if item.is_file():
        return item
    fluid = icons / "fluid" / f"{name}.png"
    if fluid.is_file():
        return fluid
    mapped = _prototype_icon(name)
    if mapped is not None and mapped.is_file():
        return mapped
    if name.endswith("-barrel"):
        barrel = icons / "fluid/barreling/empty-barrel.png"
        if barrel.is_file():
            return barrel
    return None


def _prototype_icon(name: str) -> Path | None:
    """Icône déclarée pour ``name`` dans les prototypes du jeu (carte item/fluid
    → path `__base__`/`__core__` résolu). None si introuvable."""
    mapping = _load_prototype_items()
    raw = (mapping.get(name) or {}).get("icon")
    if raw is None:
        return None
    data = _icons_dir()
    if data is None:
        return None
    base_dir = data.parent.parent  # …/data/base
    namespace = {
        "__base__": base_dir,
        "__core__": base_dir.parent / "core",
        "__terrain__": base_dir.parent / "terrain",
    }
    for token, root in namespace.items():
        if raw.startswith(token + "/"):
            path = root / raw[len(token) + 1 :]
            if path.is_file():
                return path
    return None


_PROTO_ITEMS: dict[str, dict] | None = None


def _load_prototype_items() -> dict[str, dict]:
    """Parse les prototypes Lua installés (data/base/prototypes) et renvoie
    {nom item/fluid → {"icon": …, "order": …}}, calculé une seule fois.
    Les icônes `technology/` (fiables) sont exclues."""
    global _PROTO_ITEMS
    if _PROTO_ITEMS is not None:
        return _PROTO_ITEMS
    mapping: dict[str, dict] = {}
    icons_dir = _icons_dir()
    if icons_dir is not None:
        proto_dir = icons_dir.parent.parent / "prototypes"
        if proto_dir.is_dir():
            for lua in sorted(proto_dir.rglob("*.lua")):
                parsed = _parse_prototype_items(lua.read_text(encoding="utf-8", errors="replace"))
                for n, rec in parsed.items():
                    if (rec.get("icon") or "").startswith("__") or "/technology/" not in (rec.get("icon") or ""):
                        mapping.setdefault(n, {})
                        for k, v in rec.items():
                            if k == "icon" and "/technology/" in v:
                                continue
                            mapping[n][k] = v
    _PROTO_ITEMS = mapping
    return mapping


def _parse_prototype_items(text: str) -> dict[str, dict]:
    """Extrait `type = "item"/"fluid"` + `name` → `icon`/`icons[1].icon` et
    `order` d'un fichier Lua de prototypes (découpage par accolades)."""
    mapping: dict[str, dict] = {}
    blocks = _prototype_blocks(text)
    for start, end in blocks:
        body = text[start:end]
        t = _find_line(body, 'type = "item"') or _find_line(body, 'type = "fluid"')
        if t is None:
            continue
        name = _find_quoted(body, "name = ")
        if name is None:
            continue
        rec: dict[str, str] = {}
        icon = _find_icon_in_body(body)
        if icon:
            rec["icon"] = icon
        order = _find_quoted(body, "order = ")
        if order:
            rec["order"] = order
        if rec:
            mapping[name] = rec
    return mapping


def _find_line(body: str, prefix: str) -> bool:
    for line in body.splitlines():
        if prefix in line:
            return True
    return False


_SCIENCE_ORDER = [
    "automation-science-pack", "logistic-science-pack", "military-science-pack",
    "chemical-science-pack", "production-science-pack", "utility-science-pack",
    "space-science-pack",
]
_SCIENCE_RANK = {n: i for i, n in enumerate(_SCIENCE_ORDER, start=1)}


def _find_all_quoted(body: str, key: str) -> list[str]:
    """Toutes les occurrences `key"…"` (ex. toutes les `recipe = "…"` d'un
    bloc de technologie)."""
    out: list[str] = []
    idx = 0
    needle = key + '"'
    while True:
        i = body.find(needle, idx)
        if i < 0:
            return out
        start = i + len(needle)
        j = body.find('"', start)
        if j < 0:
            return out
        out.append(body[start:j])
        idx = j + 1


_TECH_CACHE: dict[str, dict] | None = None


def _load_technologies() -> dict[str, dict]:
    """Technologies vanilla installées : {nom → {"packs": [science packs],
    "recipes": [recettes débloquées], "pre": [prérequis], "time": N}}."""
    global _TECH_CACHE
    if _TECH_CACHE is not None:
        return _TECH_CACHE
    techs: dict[str, dict] = {}
    icons_dir = _icons_dir()
    if icons_dir is not None:
        proto_dir = icons_dir.parent.parent / "prototypes"
        if proto_dir.is_dir():
            for lua in sorted(proto_dir.rglob("*.lua")):
                text = lua.read_text(encoding="utf-8", errors="replace")
                for start, end in _prototype_blocks(text):
                    body = text[start:end]
                    if not _find_line(body, 'type = "technology"'):
                        continue
                    name = _find_quoted(body, "name = ")
                    if name is None:
                        continue
                    packs = set(re.findall(r'"([a-z0-9_\-]+-science-pack)"', body))
                    recipes = set(_find_all_quoted(body, "recipe = "))
                    pre: list[str] = []
                    pm = re.search(r"prerequisites\s*=\s*\{([^}]*)\}", body)
                    if pm:
                        pre = re.findall(r'"([^"]+)"', pm.group(1))
                    tm = 0
                    tmm = re.search(r"\btime\s*=\s*(\d+)", body)
                    if tmm:
                        tm = int(tmm.group(1))
                    techs[name] = {
                        "packs": sorted(packs),
                        "recipes": sorted(recipes),
                        "pre": sorted(pre),
                        "time": tm,
                    }
    _TECH_CACHE = techs
    return techs


def _item_tech_info(seed: dict) -> dict[str, dict]:
    """Sciences ET tech(s) de déblocage de chaque item de la seed.

    La tech est celle du graphe de technologies qui débloque la recette
    (arête `unlock-recipe`). Chaque tech reçoit un **numéro d'apparition**
    (ordre topologique de l'arbre : une tech apparaît après ses prérequis,
    départagée par packs puis temps de recherche puis nom).

    Renvoie {item → {"rank": n° d'apparition (0 = aucune tech),
    "techs": [{"num": n, "name": "…"}] par numéro croissant,
    "tech": affichage "3 · logistics", "primaryTech": nom de la première,
    "science": packs requis, "scienceRank": science la plus haute}}."""
    techs = _load_technologies()
    # recette vanilla = nom de l'item produit ; la seed préfixe ses recettes
    # (randputf-…) mais PAS les noms d'items → on table sur l'item.
    tech_by_item: dict[str, set[str]] = {}
    for tname, t in techs.items():
        for r in t["recipes"]:
            tech_by_item.setdefault(r, set()).add(tname)
    # techs pertinentes : celles qui débloquent un item produit par la seed
    seed_items: dict[str, set[str]] = {}
    for recipe in seed.get("recipes") or []:
        for prod in recipe.get("results") or []:
            seed_items.setdefault(prod["name"], set()).update(
                tech_by_item.get(prod["name"], set())
            )
    relevant = set().union(*seed_items.values()) if seed_items else set()

    def trank(t: str) -> int:
        return max((_SCIENCE_RANK.get(p, 0) for p in techs[t].get("packs", [])), default=0)

    def pre_of(t: str) -> list[str]:
        return [p for p in techs[t].get("pre", []) if p in relevant]

    # numérotation : niveaux successifs de l'arbre
    order: dict[str, int] = {}
    remaining = set(relevant)
    n = 0
    while remaining:
        frontier = [t for t in remaining if all(p in order for p in pre_of(t))]
        if not frontier:  # sécurité (cycles / prérequis hors périmètre)
            frontier = [sorted(remaining)[0]]
        frontier.sort(key=lambda t: (trank(t), techs[t].get("time", 0), t))
        for t in frontier:
            n += 1
            order[t] = n
            remaining.discard(t)

    out: dict[str, dict] = {}
    for item, tnames in seed_items.items():
        ordered = sorted(tnames, key=lambda t: order[t])
        tech_list = [{"num": order[t], "name": t} for t in ordered]
        display = " + ".join(f"{o['num']} · {o['name']}" for o in tech_list)
        packs: set[str] = set()
        for t in tnames:
            packs.update(techs[t].get("packs", []))
        non_start = sorted(
            (p for p in packs if p != "start"),
            key=lambda p: _SCIENCE_RANK.get(p, 99),
        )
        out[item] = {
            "rank": order[ordered[0]] if ordered else 0,
            "techs": tech_list,
            "tech": display,
            "primaryTech": tech_list[0]["name"] if tech_list else "",
            "science": " + ".join(p.replace("-science-pack", "") for p in non_start) or "aucune",
            "scienceRank": max((_SCIENCE_RANK.get(p, 0) for p in packs), default=0),
        }
    return out


_RESOURCE_CACHE: frozenset[str] | None = None


def _load_resources() -> frozenset[str]:
    """Ressources brutes extraites sur la carte : finies (mines) et infinies
    (pompes/puits), d'après les prototypes `entity/resources.lua` du jeu."""
    global _RESOURCE_CACHE
    if _RESOURCE_CACHE is not None:
        return _RESOURCE_CACHE
    names = {"water", "wood"}
    icons_dir = _icons_dir()
    if icons_dir is not None:
        res_file = icons_dir.parent.parent / "prototypes" / "entity" / "resources.lua"
        if res_file.is_file():
            text = res_file.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'name\s*=\s*"([a-z0-9_\-]+)"', text):
                names.add(m.group(1))
    _RESOURCE_CACHE = frozenset(names)
    return _RESOURCE_CACHE


def _find_quoted(body: str, key: str) -> str | None:
    """Valeur `key"..."` (première occurrence)."""
    idx = body.find(key + '"')
    if idx < 0:
        return None
    start = idx + len(key) + 1
    end = body.find('"', start)
    if end < 0:
        return None
    return body[start:end]


def _find_icon_in_body(body: str) -> str | None:
    """`icon = "…"` simple, sinon premier `icon = "…"` d'un `icons = {…}`."""
    simple = _find_quoted(body, "icon = ")
    if simple is not None:
        return simple
    icons_idx = body.find("icons = {")
    if icons_idx >= 0:
        depth = 0
        for i in range(icons_idx, len(body)):
            c = body[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return _find_quoted(body[icons_idx:i], "icon = ")
    return None


def _prototype_blocks(text: str) -> list[tuple[int, int]]:
    """Index (début, fin) des blocs prototype d'un fichier Lua de données :
    les tables de niveau 2, sous `data:extend({ … })` — chaque prototype.
    Ignore les chaînes `"…"` (`\\"` échappées) et les commentaires `--…`."""
    stack: list[int] = []
    out: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "-" and text[i : i + 2] == "--":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
            i += 1
            continue
        if c == "{":
            stack.append(i)
        elif c == "}" and stack:
            start = stack.pop()
            if len(stack) == 1:  # niveau du prototype
                out.append((start + 1, i))
        i += 1
    return out


def build_seed_graph_dot(
    seed: dict,
    *,
    image_dir: Path | None = None,
) -> str:
    """Construit le contenu DOT du graphe de production de la seed.

    Arêtes : pour chaque recette, produit → ingrédient, label = quantité.
    Plusieurs recettes peuvent relier la même paire (primaire, relais,
    ease-up, secours) : les quantités sont alors regroupées. Ordre
    déterministe (tri) pour une sortie stable.

    ``image_dir`` : si fourni, les icônes RECADRÉES (carré/centrées, via
    ``crop_mip``) sont écrites dans ce dossier et référencées par le DOT —
    graphviz calcule alors des nœuds carrés centrés (l'original 120×64 en
    mipmap donnait des boîtes 1,875:1, l'item écrasé en haut-gauche)."""
    raw_sources: set[str] = set(ENVIRONMENTAL_ITEMS)
    raw_sources |= set((seed.get("pools") or {}).get("raw_resources") or ())

    recipes = seed.get("recipes") or []
    edges: dict[tuple[str, str], set[int]] = {}
    nodes: set[str] = set()

    for recipe in recipes:
        products = {
            res["name"] for res in (recipe.get("results") or [])
        }
        nodes |= products
        for ing in recipe.get("ingredients") or []:
            nodes.add(ing["name"])
        for product in products:
            for ing in recipe.get("ingredients") or []:
                key = (product, ing["name"])
                amount = int(ing.get("amount", 1))
                edges.setdefault(key, set()).add(amount)

    lines: list[str] = []
    for name in sorted(nodes):
        q = _quote(name)
        icon = _icon_path(name)
        img_ref = None
        if icon is not None:
            if image_dir is not None:
                fn = _slug(name) + ".png"
                try:
                    (image_dir / fn).write_bytes(crop_mip(icon.read_bytes()))
                    img_ref = f"{image_dir}/{fn}"
                except OSError:
                    img_ref = None
            else:
                img_ref = str(icon)
        if img_ref is not None:
            lines.append(
                f'  {q} [shape=box, image="{img_ref}", imagescale=true, '
                f'label="", width=0.8, height=0.8, fixedsize=true, '
                f'tooltip={q}];'
            )
        elif name in raw_sources:
            lines.append(f'  {q} [shape=ellipse, style=filled, fillcolor="#eeeeff", label={q}];')
        elif name.endswith("-science-pack"):
            lines.append(f'  {q} [shape=box, style="rounded,filled", fillcolor="#ffe8d0", label={q}];')
        else:
            lines.append(f'  {q} [shape=box, label={q}];')

    for (product, ingredient), amounts in sorted(edges.items()):
        label = ", ".join(str(a) for a in sorted(amounts))
        lines.append(f'  {_quote(product)} -> {_quote(ingredient)} [label="{label}"];')

    body = "\n".join(lines)
    footer = "\n}\n"
    return DOT_HEADER.format(seed=seed.get("meta", {}).get("seed", "?")) + body + footer


def write_seed_graph_html(seed: dict, path: Path) -> None:
    """Écrit ``path`` (HTML interactif, autonome) du graphe de la seed.

    Rendu SVG via ``dot -Tsvg`` (Graphviz requis) ; les icônes locale reconsultées
    sont embarquées en data-URI pour que le fichier soit déplaçable seul. Le
    JS intégré gère zoom/pan (molette + drag) et affiche au clic d'un nœud sa
    fiche (icône agrandie, ingrédients, utilisateurs).
    """
    dot = shutil.which("dot")
    if dot is None:
        print(f"Graphviz introuvable : l'export HTML interactif ({path}) est ignoré")
        return
    import tempfile

    with tempfile.TemporaryDirectory(prefix="randputf-graph-") as td:
        image_dir = Path(td)
        dot_path = _dot_for(seed, image_dir)
        try:
            svg = subprocess.run(
                [dot, "-Tsvg", str(dot_path)],
                capture_output=True,
                check=True,
                text=True,
            ).stdout
        finally:
            dot_path.unlink(missing_ok=True)
        svg = _embed_icons(svg)
    info = _node_info(seed)
    title = f"randputF seed {seed.get('meta', {}).get('seed', '?')}"
    path.write_text(
        _HTML_TEMPLATE.replace("__TITLE__", title)
        .replace("__SVG__", svg)
        .replace("__INFO__", json.dumps(info)),
        encoding="utf-8",
    )


def _dot_for(seed: dict, image_dir: Path | None = None) -> Path:
    """Écrit le `.dot` de la seed dans un fichier temporaire et renvoie le path
    (utilisé par write_seed_graph_html)."""
    import tempfile

    tmp = tempfile.NamedTemporaryFile("w", suffix=".dot", delete=False, encoding="utf-8")
    try:
        tmp.write(build_seed_graph_dot(seed, image_dir=image_dir))
        tmp.flush()
    finally:
        tmp.close()
    return Path(tmp.name)


_ICON_HREF_RE = re.compile(r'(xlink:href|href)="([^"]+\.png)"')


def _embed_icons(svg: str) -> str:
    """Remplace les `href` d'icônes locales par des data-URI base64 (SVG autonome)."""
    def _uri(m: re.Match) -> str:
        attr, path = m.group(1), m.group(2)
        try:
            b64 = base64.b64encode(crop_mip(Path(path).read_bytes())).decode()
        except OSError:
            return m.group(0)
        return f'{attr}="data:image/png;base64,{b64}"'
    return _ICON_HREF_RE.sub(_uri, svg)


def _node_info(seed: dict) -> dict[str, dict]:
    """Fiche de chaque nœud pour l'interface : voisins (ingrédients / produits
    qui l'utilisent), tech(s) de déblocage et icône embarquée en data-URI."""
    info: dict[str, dict] = {}
    for recipe in seed.get("recipes") or []:
        products = [res["name"] for res in (recipe.get("results") or [])]
        ingredients = [ing["name"] for ing in (recipe.get("ingredients") or [])]
        for p in products:
            for ing in ingredients:
                info.setdefault(p, {}).setdefault("ingredients", []).append(ing)
                info.setdefault(ing, {}).setdefault("used_by", []).append(p)
    tinfo = _item_tech_info(seed)
    resources = _load_resources()
    for name, rec in info.items():
        t = tinfo.get(name)
        rec["raw"] = name in resources
        rec["rank"] = t["rank"] if t else 0
        rec["techs"] = t["techs"] if t else []
        rec["tech"] = t["tech"] if t else ""
        rec["primaryTech"] = t["primaryTech"] if t else ""
        rec["science"] = t["science"] if t else ""
        rec["scienceRank"] = t["scienceRank"] if t else 0
        icon = _icon_path(name)
        if icon is not None:
            try:
                rec["icon"] = "data:image/png;base64," + base64.b64encode(crop_mip(icon.read_bytes())).decode()
            except OSError:
                pass
    return info


_HTML_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>__TITLE__ - graphe interactif</title>
<style>
  :root {
    --bg: #141419;
    --panel: rgba(32,32,40,.92);
    --line: #3a3a45;
    --txt: #d7d7e0;
    --muted: #8f8fa0;
    --edge: #e8e8f0;
    --focus: #ffffff;
    --nodebg: #2a2a32;
    --field: #1b1b22;
    --glow: rgba(255,255,255,.95);
    --hl0: #ffd54f; --hl1: #ff7043; --hl2: #f06292; --hl3: #ab47bc;
    --hl4: #5c6bc0; --hl5: #29b6f6; --hl6: #26a69a; --hl7: #9ccc65;
  }
  body.day {
    --bg: #ffffff;
    --panel: rgba(255,255,255,.95);
    --line: #d5d5df;
    --txt: #1c1c26;
    --muted: #6f6f7f;
    --edge: #1c1c26;
    --focus: #12121a;
    --nodebg: #e8e8f0;
    --field: #f1f1f5;
    --glow: rgba(0,0,0,.45);
  }
  * { box-sizing: border-box; }
  html, body { margin:0; height:100%; overflow:hidden;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--txt); }
  ::-webkit-scrollbar { width:10px; }
  ::-webkit-scrollbar-thumb { background:#333; border-radius:5px; }
  /* ---- panneau latéral ---- */
  #sidebar { position:absolute; left:0; top:0; bottom:0; width:290px; z-index:7;
    display:flex; flex-direction:column; background:var(--panel);
    border-right:1px solid var(--line); }
  #sidebar header { padding:10px 14px; border-bottom:1px solid var(--line); }
  #sidebar h1 { margin:0; font-size:14px; }
  #sidebar #subtitle { color:var(--muted); font-size:11px; margin-top:2px; }
  #tools { padding:8px; border-bottom:1px solid var(--line);
    display:flex; flex-direction:column; gap:7px; }
  #search { width:100%; padding:8px 12px; border:1px solid var(--line); border-radius:8px;
    background:var(--field); color:var(--txt); font-size:12px; outline:none; }
  #search:focus { border-color:#6f6fe6; box-shadow:0 0 0 3px rgba(111,111,230,.22); }
  #sorts { display:flex; gap:6px; }
  .sortbtn { flex:1; padding:6px; border:1px solid var(--line); border-radius:7px;
    background:transparent; color:var(--muted); cursor:pointer; font-size:12px; }
  .sortbtn:hover { color:var(--txt); }
  .sortbtn.active { background:#3a3af0; border-color:#6f6fe6; color:#fff; }
  #list { flex:1; overflow-y:auto; padding:6px 8px 12px; }
  .grp { margin:10px 2px 4px; font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); font-weight:700; }
  .grp:first-child { margin-top:2px; }
  .row { display:flex; align-items:center; gap:8px; padding:3px 8px; border-radius:7px;
    cursor:pointer; font-size:12px; border-left:4px solid transparent; white-space:nowrap; }
  .row:hover { background:rgba(255,255,255,.07); }
  .row.dim { opacity:.25; }
  .row img { width:30px; height:30px; flex:none; image-rendering:pixelated;
    object-fit:contain; object-position:center; }
  .row span { overflow:hidden; text-overflow:ellipsis; }
  .row .sc { margin-left:auto; flex:none; font-size:10px; color:var(--muted); font-weight:700; }
  /* ---- viewer ---- */
  #viewer { position:absolute; inset:0 0 0 290px; }
  #biggraph, #minigraph { position:absolute; inset:0; }
  #biggraph svg { background: var(--bg); transform-origin:0 0; }
  /* ---- mode jour/nuit sur le SVG graphviz (style en dur) ---- */
  #biggraph svg polygon[fill="#141419"] { fill: var(--bg) !important; }
  #biggraph g.edge path:not([style]) { stroke: var(--edge) !important; }
  #biggraph polygon[stroke="black"], #biggraph ellipse[stroke="black"] { stroke: var(--edge) !important; }
  #biggraph polygon[fill="black"] { fill: var(--edge) !important; }
  #biggraph text { fill: var(--txt) !important; }
  /* ---- mini-graphe (SVG dynamique) ---- */
  #minigraph rect[fill="#2a2a32"] { fill: var(--nodebg) !important; }
  #minigraph rect[stroke="#ffffff"], #minigraph rect[stroke="white"] { stroke: var(--focus) !important; }
  #minigraph text[fill="#d7d7e0"] { fill: var(--txt) !important; }
  #minigraph { display:none; position:absolute; inset:0; overflow:hidden; cursor:grab; }
  #minigraph svg { position:absolute; left:0; top:0; transform-origin:0 0; }
  #minigraph:active { cursor:grabbing; }
  #minigraph .mininode { cursor:pointer; }
  #minigraph .mininode image { image-rendering: pixelated; }
  #minigraph .mininode rect { transition: filter .2s; }
  #minigraph .mininode:hover rect { filter: brightness(1.35); }
  #viewer g.node { cursor:pointer; transition: filter .25s ease; }
  #viewer g.node image { image-rendering: pixelated; }
  #viewer g.node.dim, #viewer g.node .dim { opacity:.1; }
  #viewer g.node.hl-focus { filter: drop-shadow(0 0 12px var(--glow)); }
  #viewer g.node.hl-c0 { filter: drop-shadow(0 0 10px var(--hl0)); }
  #viewer g.node.hl-c1 { filter: drop-shadow(0 0 10px var(--hl1)); }
  #viewer g.node.hl-c2 { filter: drop-shadow(0 0 10px var(--hl2)); }
  #viewer g.node.hl-c3 { filter: drop-shadow(0 0 10px var(--hl3)); }
  #viewer g.node.hl-c4 { filter: drop-shadow(0 0 10px var(--hl4)); }
  #viewer g.node.hl-c5 { filter: drop-shadow(0 0 10px var(--hl5)); }
  #viewer g.node.hl-c6 { filter: drop-shadow(0 0 10px var(--hl6)); }
  #viewer g.node.hl-c7 { filter: drop-shadow(0 0 10px var(--hl7)); }
  #viewer g.node:not(.dim):hover { filter: brightness(1.3); }
  #viewer g.edge path { transition: stroke .25s ease; }
  /* ---- fenêtres ---- */
  .ui { position:absolute; z-index:6; background:var(--panel);
    border:1px solid var(--line); border-radius:10px; backdrop-filter: blur(6px); }
  #subonly { top:10px; right:10px; padding:8px 12px; font-size:12px;
    display:flex; align-items:center; gap:8px; cursor:pointer; }
  #subonly input { accent-color:#6f6fe6; }
  #theme { top:10px; left:300px; padding:8px 12px; font-size:12px; cursor:pointer;
    color:var(--txt); user-select:none; }
  #theme:hover { border-color:var(--txt); }
  #panel { top:58px; right:10px; width:250px; padding:14px; display:none; font-size:13px;
    max-height:calc(100% - 70px); overflow-y:auto; }
  #panel h3 { margin:0 0 6px; font-size:15px; word-break: break-word; }
  #panel img { width:96px; height:96px; float:right; margin:0 0 8px 8px; image-rendering: pixelated;
    border:1px solid var(--line); border-radius:6px; background:var(--field);
    object-fit:contain; object-position:center; }
  #panel ul { margin:8px 0 0; padding:0; list-style:none; }
  #panel li { padding:3px 8px; margin:2px 0; border-radius:6px; font-size:12px; color:var(--txt);
    background:rgba(255,255,255,.05); cursor:pointer; }
  #panel li:hover { background:rgba(255,255,255,.12); }
  #panel .sep { margin-top:10px; font-size:11px; text-transform:uppercase; letter-spacing:.06em;
    color:var(--muted); border-top:1px solid var(--line); padding-top:8px; }
  #panel .sci { color:#9ccc65; font-size:12px; margin-bottom:6px; font-weight:700; }
  #close { float:right; cursor:pointer; color:var(--muted); font-size:15px; line-height:1; }
  #close:hover { color:var(--txt); }
  #depthkey { bottom:12px; right:10px; padding:10px 12px; font-size:11px; color:var(--muted); display:none; }
  #depthkey b { float:left; width:12px; height:12px; margin:2px 8px 2px 0; border-radius:3px; }
  #depthkey div { clear:both; }
  #limit { position:fixed; inset:0; z-index:99; display:none; flex-direction:column; gap:12px;
    align-items:center; justify-content:center; text-align:center; padding:40px; font-size:14px; }
</style>
</head>
<body>
<aside id="sidebar">
  <header><h1>__TITLE__</h1><div id="subtitle">graphe interactif — cliquez un objet pour sa cascade</div></header>
  <div id="tools">
    <input id="search" placeholder="Rechercher dans le panneau… (Échap pour effacer)">
    <div id="sorts">
      <button class="sortbtn active" data-sort="science" title="Trier par tech de déblocage dans l'arbre">Tech</button>
      <button class="sortbtn" data-sort="name" title="Trier par nom">Nom</button>
    </div>
  </div>
  <div id="list"></div>
</aside>
<div id="viewer">
  <div id="biggraph">__SVG__</div>
  <div id="minigraph"></div>
</div>
<label id="subonly" class="ui" title="Ne garder que l'objet choisi et ses dépendances">
  <input type="checkbox" id="subcheck"><span>Sous-graphe : seulement les dépendances</span>
</label>
<button id="theme" class="ui" title="Basculer le mode jour / nuit"></button>
<div id="depthkey" class="ui"></div>
<div id="panel" class="ui"><span id="close">✕</span><div id="fiche"></div></div>
<div id="limit"><b>Graphe trop grand — impossible à afficher</b><span id="limitmsg"></span></div>
<script>
const MAX_NODES = 1500;
const INFO = __INFO__;
const PALETTE = ['#ffd54f','#ff7043','#f06292','#ab47bc','#5c6bc0','#29b6f6','#26a69a','#9ccc65'];
const viewer = document.getElementById('viewer');
const svg = viewer.querySelector('svg');
const graphEl = svg.querySelector('g.graph');
const childOrder = Array.from(graphEl.children);
const panel = document.getElementById('panel');
const fiche = document.getElementById('fiche');
const depthkey = document.getElementById('depthkey');
const list = document.getElementById('list');
const search = document.getElementById('search');
const subcheck = document.getElementById('subcheck');
const subonly = document.getElementById('subonly');
const biggraph = document.getElementById('biggraph');
const minigraph = document.getElementById('minigraph');
let sortMode = 'science', lastSel = null, subOnly = false;
let rowEls = {}, lastNodes = [], lastEdges = [], lastRows = [], lastSub = [], lastDepth = null;
/* ---- garde anti-performance ---- */
const count = Object.keys(INFO).length;
if (count > MAX_NODES) {
  document.getElementById('limitmsg').textContent =
    count + ' objets dans la seed (maximum ' + MAX_NODES + '). Impossible ' + "d'afficher le graphe interactif.";
  document.getElementById('limit').style.display = 'flex';
} else {
  boot();
}
function boot() {
  /* ---- pan / zoom ---- */
  let k = 1, tx = 0, ty = 0, dragging = false, mx = 0, my = 0;
  function apply() { svg.style.transform = `translate(${tx}px,${ty}px) scale(${k})`; }
  const box = svg.viewBox.baseVal;
  svg.setAttribute('width', box.width); svg.setAttribute('height', box.height);
  function fit() {
    k = Math.max(0.05, Math.min(3, innerWidth / box.width));
    tx = (innerWidth - box.width*k)/2; ty = 24; apply();
  }
  addEventListener('resize', fit); fit();
  viewer.addEventListener('dblclick', () => { if (!subOnly) fit(); });
  viewer.addEventListener('wheel', e => {
    e.preventDefault();
    if (subOnly) return;
    const f = Math.exp(-e.deltaY*0.0015);
    k = Math.max(0.03, Math.min(50, k*f));
    const r = svg.getBoundingClientRect();
    tx += (e.clientX - r.left)*(1-f); ty += (e.clientY - r.top)*(1-f); apply();
  }, {passive:false});
  viewer.addEventListener('mousedown', e => { if (!subOnly) { dragging = true; mx = e.clientX; my = e.clientY; } });
  addEventListener('mouseup', () => { dragging = false; });
  viewer.addEventListener('mousemove', e => {
    if (!dragging) return;
    tx += e.clientX - mx; ty += e.clientY - my; mx = e.clientX; my = e.clientY; apply();
  });
  /* ---- mini-graphe : déplacement / zoom ---- */
  let miniK = 1, miniTX = 0, miniTY = 0, miniDrag = null, miniMoved = false;
  function miniSvgApply() {
    const ms = minigraph.querySelector('svg');
    if (!ms) return;
    ms.style.transformOrigin = '0 0';
    ms.style.transform = 'translate(' + miniTX + 'px,' + miniTY + 'px) scale(' + miniK + ')';
  }
  function miniReset() {
    miniK = 1; miniTX = 0; miniTY = 0; miniDrag = null; miniMoved = false; miniSvgApply();
  }
  function miniFit() {
    /* Affiche le mini-graphe EN ENTIER (plus de partie basse/droite mangée)
       dans la zone NON recouverte par les panneaux flottants : on retire
       de la place visible la fiche, la légende de profondeur, l'option
       sous-graphe et le bouton thème, puis on centre dans le reste. */
    const ms = minigraph.querySelector('svg');
    if (!ms) return;
    const w = parseFloat(ms.getAttribute('width')) || 1;
    const h = parseFloat(ms.getAttribute('height')) || 1;
    const vr = minigraph.getBoundingClientRect();
    const vw = vr.width || innerWidth;
    const vh = vr.height || innerHeight;
    let leftIn = 0, topIn = 0, rightIn = 0, botIn = 0;
    const overlays = [panel, depthkey, subonly, document.getElementById('theme')];
    for (const el of overlays) {
      if (!el) continue;
      let r;
      try {
        if (getComputedStyle(el).display === 'none') continue;
        r = el.getBoundingClientRect();
      } catch (e) { continue; }
      const rl = +r.left || 0, rt = +r.top || 0, rw = +r.width || 0, rh = +r.height || 0;
      const right = rl + rw, bottom = rt + rh;
      if (right <= vr.left || rl >= vr.left + vw || bottom <= vr.top || rt >= vr.top + vh) continue;
      leftIn = Math.max(leftIn, Math.min(vw, Math.max(0, right - vr.left)));
      rightIn = Math.max(rightIn, Math.min(vw, Math.max(0, vr.left + vw - rl)));
      topIn = Math.max(topIn, Math.min(vh, Math.max(0, bottom - vr.top)));
      botIn = Math.max(botIn, Math.min(vh, Math.max(0, vr.top + vh - rt)));
    }
    cw = vw - rightIn;
    ch = vh - botIn;
    miniK = Math.max(0.05, Math.min(1, Math.min((cw - 24) / w, (ch - 24) / h)));
    miniTX = leftIn + (cw - w * miniK) / 2;
    miniTY = topIn + (ch - h * miniK) / 2;
    miniSvgApply();
  }
  minigraph.addEventListener('wheel', e => {
    e.preventDefault(); e.stopPropagation();
    if (minigraph.style.display === 'none') return;
    const f = Math.exp(-e.deltaY * 0.0022);
    miniK = Math.max(0.1, Math.min(8, miniK * f));
    const r = minigraph.querySelector('svg').getBoundingClientRect();
    miniTX += (e.clientX - r.left) * (1 - f);
    miniTY += (e.clientY - r.top) * (1 - f);
    miniSvgApply();
  }, {passive:false});
  minigraph.addEventListener('mousedown', e => {
    if (e.button !== 0) return;
    miniDrag = { x: e.clientX, y: e.clientY }; miniMoved = false;
    e.stopPropagation();
  });
  addEventListener('mousemove', e => {
    if (!miniDrag) return;
    const dx = e.clientX - miniDrag.x, dy = e.clientY - miniDrag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) miniMoved = true;
    miniDrag = { x: e.clientX, y: e.clientY };
    miniTX += dx; miniTY += dy; miniSvgApply();
  });
  addEventListener('mouseup', () => {
    miniDrag = null;
    setTimeout(() => { miniMoved = false; }, 0);
  });
  minigraph.addEventListener('dblclick', () => { miniFit(); });
  hideSubOption();
  /* ---- index du graphe ---- */
  const nodeEls = {};
  document.querySelectorAll('#viewer g.node').forEach(g => {
    const t = g.querySelector('title');
    if (t) nodeEls[t.textContent.trim()] = g;
  });
  const edgeEls = [];
  document.querySelectorAll('#viewer g.edge').forEach(g => {
    const t = g.querySelector('title');
    if (!t) return;
    const parts = t.textContent.split('->');
    if (parts.length < 2) return;
    edgeEls.push({ from: parts[0].trim(), to: parts[1].trim(), el: g, path: g.querySelector('path') });
  });
  function colorOf(depth) { return PALETTE[(depth - 1) % PALETTE.length]; }
  /* ---- surlignage en cascade ---- */
  function clearHigh() {
    lastNodes.forEach(o => { o.el.classList.remove('dim','hl-focus'); PALETTE.forEach((_,i)=>o.el.classList.remove('hl-c'+i)); });
    lastEdges.forEach(o => { if (o.path) o.path.removeAttribute('style'); });
    lastRows.forEach(r => { r.classList.remove('dim'); r.style.borderLeftColor=''; });
    lastSub.forEach(el => { el.style.display = ''; });
    lastNodes = []; lastEdges = []; lastRows = []; lastSub = []; lastDepth = null;
    childOrder.forEach(el => graphEl.appendChild(el));
    depthkey.style.display = 'none';
  }
  function highlight(name) {
    clearHigh();
    const depth = {}; depth[name] = 0;
    const q = [name];
    while (q.length) {
      const cur = q.shift();
      for (const x of (INFO[cur]||{}).ingredients || []) {
        if (depth[x] !== undefined) continue;
        depth[x] = depth[cur] + 1; q.push(x);
      }
    }
    let maxD = 0;
    for (const d of Object.values(depth)) maxD = Math.max(maxD, d);
    const hlNodes = [];
    for (const [n, d] of Object.entries(depth)) {
      const g = nodeEls[n]; if (!g) continue;
      g.classList.remove('dim');
      if (d === 0) g.classList.add('hl-focus');
      else g.classList.add('hl-c' + ((d-1) % PALETTE.length));
      hlNodes.push({el:g, depth:d});
    }
    for (const g of Object.values(nodeEls)) {
      const t = g.querySelector('title');
      if (!t || depth[t.textContent.trim()] === undefined) {
        g.classList.add('dim'); lastNodes.push({el:g});
      }
    }
    const picked = [];
    for (const e of edgeEls) {
      const pa = depth[e.from], ch = depth[e.to];
      if (pa !== undefined && ch === pa + 1) {
        if (e.path) e.path.style.stroke = colorOf(ch);
        picked.push(e); lastEdges.push(e);
      }
    }
    lastNodes = lastNodes.concat(hlNodes);
    lastDepth = depth;
    if (subOnly) {
      for (const [n, g] of Object.entries(nodeEls)) {
        if (depth[n] === undefined) { g.style.display = 'none'; lastSub.push(g); }
      }
      const pickedEls = new Set(picked.map(e => e.el));
      for (const e of edgeEls) {
        if (!pickedEls.has(e.el)) { e.el.style.display = 'none'; lastSub.push(e.el); }
      }
    }
    picked.sort((a,b) => depth[a.to] - depth[b.to]).forEach(e => graphEl.appendChild(e.el));
    hlNodes.sort((a,b) => a.depth - b.depth).forEach(o => graphEl.appendChild(o.el));
    /* couleurs de la cascade en miroir dans le panneau */
    for (const n of Object.keys(rowEls)) {
      const r = rowEls[n];
      if (depth[n] === undefined) { r.classList.add('dim'); lastRows.push(r); }
      else { r.classList.remove('dim'); r.style.borderLeftColor = n === name ? focusCol() : colorOf(depth[n]); lastRows.push(r); }
    }
    buildDepthKey(maxD);
  }
  function buildDepthKey(maxD) {
    depthkey.innerHTML = '';
    for (let d = 1; d <= Math.max(1, Math.min(maxD, 8)); d++) {
      const row = document.createElement('div');
      const chip = document.createElement('b');
      chip.style.background = colorOf(d);
      row.appendChild(chip);
      row.appendChild(document.createTextNode('ingrédients niveau ' + d));
      depthkey.appendChild(row);
    }
    depthkey.style.display = 'block';
  }
  function buildFiche(name) {
    fiche.innerHTML = '';
    const img = nodeEls[name] && nodeEls[name].querySelector('image');
    if (img) {
      const i = document.createElement('img');
      i.src = img.getAttribute('xlink:href') || img.getAttribute('href');
      fiche.appendChild(i);
    }
    const h = document.createElement('h3'); h.textContent = name; fiche.appendChild(h);
    const info = INFO[name] || {};
    if (info.rank > 0 && info.tech) {
      const d = document.createElement('div'); d.className = 'sci';
      d.textContent = 'Débloqué par : ' + info.tech;
      fiche.appendChild(d);
    }
    const mk = (label, list) => {
      if (!list || !list.length) return;
      const sep = document.createElement('div'); sep.className = 'sep'; sep.textContent = label + ' (' + list.length + ')';
      fiche.appendChild(sep);
      const u = document.createElement('ul');
      for (const x of [...new Set(list)]) {
        const li = document.createElement('li');
        li.textContent = x;
        li.addEventListener('click', () => { select(x); });
        u.appendChild(li);
      }
      fiche.appendChild(u);
    };
    mk('Ingrédients', info.ingredients);
    mk('Utilisé par', info.used_by);
  }
  function select(name, src) {
    buildFiche(name);
    panel.style.display = 'block';
    showSubOption();
    if (src === 'mini') {
      // navigation DANS le sous-graphe : on le garde actif
      subcheck.checked = true; subOnly = true;
      buildMini(name);
    } else {
      // sélection sur le grand graphe (ligne, nœud, fiche) : on y reste
      subcheck.checked = false; subOnly = false;
      removeMini();
      highlight(name);
    }
    lastSel = name;
  }
  function removeMini() {
    // vrai changement mini → grand graphe : on remet le zoom par défaut
    const fromMini = minigraph.style.display === 'block';
    minigraph.style.display = 'none';
    minigraph.innerHTML = '';
    biggraph.style.display = '';
    miniReset();
    if (fromMini) fit();
  }
  function showSubOption() {
    subonly.style.display = '';
  }
  function hideSubOption() {
    subonly.style.display = 'none';
  }
  function escXml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function buildMini(name) {
    clearHigh();
    const depth = {}; depth[name] = 0;
    const q = [name];
    while (q.length) {
      const cur = q.shift();
      for (const x of (INFO[cur] || {}).ingredients || []) {
        if (depth[x] !== undefined) continue;
        depth[x] = depth[cur] + 1; q.push(x);
      }
    }
    const levels = {};
    for (const [n, d] of Object.entries(depth)) (levels[d] = levels[d] || []).push(n);
    for (const arr of Object.values(levels)) arr.sort((a, b) => a.localeCompare(b));
    let maxCol = 0;
    for (const arr of Object.values(levels)) maxCol = Math.max(maxCol, arr.length);
    const W = 64, H = 64, LH = 14, HGAP = 104, VGAP = 12, PAD = 12;
    const colH = arr => arr.length * (H + LH) + (arr.length - 1) * VGAP;
    const lvl = Object.keys(levels).map(Number).sort((a, b) => a - b);
    const width = lvl.length * (W + HGAP) - HGAP + PAD * 2;
    const height = maxCol * (H + LH) + (maxCol - 1) * VGAP + PAD * 2;
    const pos = {};
    for (const [n, d] of Object.entries(depth)) {
      const arr = levels[d], i = arr.indexOf(n);
      const x = PAD + d * (W + HGAP);
      const y = PAD + (height - PAD * 2 - colH(arr)) / 2 + i * (H + LH + VGAP);
      pos[n] = { x: x + W / 2, y: y + H / 2 };
    }
    let svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + width + '" height="' + height + '">';
    const seen = new Set();
    for (const [n, d] of Object.entries(depth)) {
      for (const x of (INFO[n] || {}).ingredients || []) {
        if (depth[x] !== d + 1) continue;
        const key = x + '>' + n;
        if (seen.has(key)) continue;
        seen.add(key);
        const p = pos[n], c = pos[x];
        const col = colorOf(depth[x]);
        svg += '<path d="M ' + p.x + ' ' + p.y + ' C ' + (p.x + 24) + ' ' + p.y + ', ' + (c.x - 24) + ' ' + c.y + ', ' + c.x + ' ' + c.y + '" fill="none" stroke="' + col + '" stroke-width="2"/>';
      }
    }
    for (const [n, d] of Object.entries(depth)) {
      const arr = levels[d], i = arr.indexOf(n);
      const x = PAD + d * (W + HGAP);
      const y = PAD + (height - PAD * 2 - colH(arr)) / 2 + i * (H + LH + VGAP);
      const info = INFO[n] || {};
      const col = n === name ? focusCol() : colorOf(d);
      svg += '<g class="mininode" data-name="' + escXml(n) + '" transform="translate(' + x + ' ' + y + ')">';
      svg += '<title>' + escXml(n) + '</title>';
      svg += '<rect width="' + W + '" height="' + H + '" rx="8" fill="#2a2a32" stroke="' + col + '" stroke-width="' + (n === name ? 3 : 2) + '"/>';
      if (info.icon) svg += '<image href="' + info.icon + '" x="4" y="4" width="56" height="56" preserveAspectRatio="xMidYMid meet"/>';
      if (n === name) svg += '<text x="' + (W / 2) + '" y="' + (H + 11) + '" text-anchor="middle" font-size="10" fill="#d7d7e0">' + escXml(n) + '</text>';
      svg += '</g>';
    }
    svg += '</svg>';
    const wasHidden = minigraph.style.display === 'none';
    minigraph.innerHTML = svg;
    minigraph.style.display = 'block';
    biggraph.style.display = 'none';
    // le sous-graphe s'affiche EN ENTIER lors d'un changement de nœud ou
    // d'une première ouverture ; sinon l'utilisateur garde son zoom/déplacement.
    if (name !== lastSel || wasHidden) miniFit(); else miniSvgApply();
    for (const n of Object.keys(rowEls)) {
      const r = rowEls[n];
      if (depth[n] === undefined) { r.classList.add('dim'); lastRows.push(r); }
      else { r.classList.remove('dim'); r.style.borderLeftColor = n === name ? focusCol() : colorOf(depth[n]); lastRows.push(r); }
    }
    buildDepthKey(maxLevel(depth));
    minigraph.querySelectorAll('.mininode').forEach(g => {
      g.addEventListener('click', () => {
        if (miniMoved) { miniMoved = false; return; }
        select(g.getAttribute('data-name'), 'mini');
      });
    });
  }
  function maxLevel(depth) {
    let m = 0;
    for (const v of Object.values(depth)) m = Math.max(m, v);
    return m;
  }
  viewer.addEventListener('click', e => {
    if (dragging) return;
    const g = e.target.closest('g.node');
    if (!g) return; // clic à côté : la sélection est conservée
    const t = g.querySelector('title');
    select(t ? t.textContent.trim() : '?');
  });
  document.getElementById('close').addEventListener('click', () => {
    clearHigh(); removeMini(); panel.style.display = 'none';
    lastSel = null; subcheck.checked = false; subOnly = false; hideSubOption();
  });
  subcheck.addEventListener('change', () => {
    if (subcheck.checked) {
      if (lastSel) select(lastSel, 'mini');
    } else {
      subOnly = false;
      removeMini();
      if (lastSel) highlight(lastSel);
    }
  });
  /* ---- mode jour / nuit : noir et blanc s'inversent, le reste ne bouge pas ---- */
  function focusCol() {
    try { return getComputedStyle(document.documentElement).getPropertyValue('--focus').trim() || '#ffffff'; }
    catch (e) { return '#ffffff'; }
  }
  const themeBtn = document.getElementById('theme');
  function setTheme(day) {
    document.body.classList.toggle('day', !!day);
    themeBtn.textContent = day ? 'Nuit' : 'Jour';
    themeBtn.title = day ? 'Mode nuit (fond noir, branches blanches) — cliquer pour passer en jour' : 'Mode jour (fond blanc, branches noires) — cliquer pour passer en nuit';
    try { localStorage.setItem('randputfTheme', day ? 'day' : 'night'); } catch (e) {}
    if (lastSel) { if (subOnly) buildMini(lastSel); else highlight(lastSel); }
  }
  themeBtn.addEventListener('click', () => setTheme(!document.body.classList.contains('day')));
  try { setTheme(localStorage.getItem('randputfTheme') === 'day'); } catch (e) { setTheme(false); }
  /* ---- panneau : recherche + tri + liste ---- */
  search.addEventListener('input', () => {
    clearHigh(); removeMini(); panel.style.display = 'none';
    lastSel = null; subcheck.checked = false; subOnly = false; hideSubOption(); renderList();
  });
  addEventListener('keydown', e => { if (e.key === 'Escape') { search.value=''; search.dispatchEvent(new Event('input')); } });
  document.querySelectorAll('.sortbtn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.sortbtn').forEach(x => x.classList.toggle('active', x === b));
    sortMode = b.dataset.sort; renderList();
  }));
  function renderList() {
    list.innerHTML = ''; rowEls = {};
    const q = search.value.trim().toLowerCase();
    let entries = Object.entries(INFO).filter(([n]) => !q || n.toLowerCase().includes(q));
    const gkey = rec => (rec.raw ? -1 : (rec.rank > 0 ? rec.rank + 1 : 0));
    if (sortMode === 'science') {
      entries.sort((a,b) => gkey(a[1]) - gkey(b[1]) || a[0].localeCompare(b[0]));
    } else {
      entries.sort((a,b) => a[0].localeCompare(b[0]));
    }
    let grp = null;
    for (const [n, rec] of entries) {
      if (sortMode === 'science') {
        const g0 = gkey(rec);
        if (g0 !== grp) {
          grp = g0;
          const hd = document.createElement('div'); hd.className = 'grp';
          hd.textContent = g0 < 0 ? 'Ressources brutes (finies + infinies)'
            : (g0 === 0 ? 'Starter' : (g0 - 1) + ' · ' + (rec.primaryTech || rec.tech));
          list.appendChild(hd);
        }
      }
      const row = document.createElement('div'); row.className = 'row';
      if (rec.icon) {
        const im = document.createElement('img'); im.src = rec.icon; row.appendChild(im);
      }
      const sp = document.createElement('span'); sp.textContent = n; row.appendChild(sp);
      if (rec.tech && sortMode === 'science' && !rec.raw) {
        const b = document.createElement('b'); b.className = 'sc'; b.textContent = rec.tech; row.appendChild(b);
      }
      row.addEventListener('click', () => select(n));
      rowEls[n] = row; list.appendChild(row);
    }
    if (!entries.length) {
      const e = document.createElement('div'); e.className = 'grp'; e.textContent = 'aucun résultat';
      list.appendChild(e);
    }
  }
  renderList();
}
</script>
</body>
</html>
"""


def _quote(name: str) -> str:
    """Identifiant DOT entre guillemets (échappement `"` et `\\`, newline→\\n)."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


_SLUG_RE = re.compile(r"[^A-Za-z0-9_.\-]")


def _slug(name: str) -> str:
    """Nom de fichier sûr pour une icône recadrée (l'item "water\"X" → water_X)."""
    return _SLUG_RE.sub("_", name)