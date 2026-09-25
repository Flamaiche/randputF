"""Export du graphe de production d'une seed.

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


def _tech_order(seed: dict) -> tuple[dict, dict[str, int], set[str], dict[str, list[str]]]:
    """Ordre de progression commun : {tech → n° d'apparition 1..N} (positions
    manquantes comblées par parcours topologique), techs starter ``free`` et
    mapping recette → produits pour attribuer les déblocages. """
    tmap = {t.get("id"): t for t in (seed.get("technologies") or []) if t.get("id")}
    prog = list(seed.get("progression_order") or [])
    order: dict[str, int] = {}
    for i, tid in enumerate(prog):
        if tid in tmap:
            order[tid] = i + 1
    missing = set(tmap) - set(order)
    if missing:
        n = len(order)
        while missing:
            frontier = [t for t in missing if all(p in order for p in (tmap[t].get("prerequisites") or []))]
            if not frontier:  # sécurité (cycles / prérequis hors périmètre)
                frontier = sorted(missing)
            frontier.sort(key=lambda t: tmap[t].get("localised_name") or t)
            for t in frontier:
                n += 1
                order[t] = n
                missing.discard(t)
    free = set(seed.get("free_researches") or [])
    rec_by_recipe: dict[str, list[str]] = {}
    for recipe in seed.get("recipes") or []:
        rec_by_recipe[recipe.get("name", "")] = [
            res.get("name", "") for res in recipe.get("results") or []
        ]
    return tmap, order, free, rec_by_recipe


def _recipe_tech_info(seed: dict) -> dict[str, dict]:
    """Même attribution que _item_tech_info mais RAMENÉE AUX RECETTES : une
    recette est déblocable par les techs du seed qui la débloquent (une recette
    multi-produit compterait pour chaque produit — ici toutes mono-produit).
    Renvoie {recette → {"num": rang (0 = starter), "name": tech principale,
    "tech": affichage "3 · nom + 5 · nom"}}."""
    tmap, order, free, _ = _tech_order(seed)

    def local(tid: str) -> str:
        return tmap[tid].get("localised_name") or tid

    unlocks: dict[str, list[tuple[int, str]]] = {}
    for tid, num in order.items():
        for eff in tmap[tid].get("effects") or []:
            if eff.get("type") != "unlock-recipe":
                continue
            unlocks.setdefault(eff.get("recipe", ""), []).append((num, tid))
    out: dict[str, dict] = {}
    for rname, lst in unlocks.items():
        items = sorted(lst)
        reals = [(num, tid) for (num, tid) in items if tid not in free]
        num = min((n for n, _ in reals), default=0)
        out[rname] = {
            "num": num,
            "name": local(items[0][1]) if items else "",
            "tech": " + ".join(f"{n} · {local(tid)}" for n, tid in items),
            "techs": [
                {"id": tid, "num": n, "name": local(tid), "free": tid in free}
                for n, tid in items
            ],
        }
    return out


def _technology_info(seed: dict) -> dict[str, dict]:
    tmap, order, free, _ = _tech_order(seed)
    recipe_products: dict[str, str] = {}
    for recipe in seed.get("recipes") or []:
        results = recipe.get("results") or []
        if results and results[0].get("name"):
            recipe_products[recipe.get("name", "")] = results[0]["name"]

    out: dict[str, dict] = {}
    for tid, tech in tmap.items():
        unit = tech.get("unit") or {}
        try:
            count = int(unit.get("count", 1) or 1)
        except (TypeError, ValueError):
            count = 1
        count = max(count, 1)
        ingredients = []
        for ingredient in unit.get("ingredients") or []:
            name = ingredient.get("name")
            if not name:
                continue
            try:
                amount = int(ingredient.get("amount", 1) or 1)
            except (TypeError, ValueError):
                amount = 1
            ingredients.append({"name": name, "amount": amount * count})

        unlocks = []
        seen: set[str] = set()
        for effect in tech.get("effects") or []:
            if effect.get("type") != "unlock-recipe":
                continue
            recipe = effect.get("recipe")
            if not recipe or recipe in seen:
                continue
            seen.add(recipe)
            unlocks.append({
                "recipe": recipe,
                "product": recipe_products.get(recipe, recipe.removeprefix("randputf-")),
            })

        prerequisites = []
        for prerequisite in tech.get("prerequisites") or []:
            if not prerequisite:
                continue
            prerequisite_tech = tmap.get(prerequisite) or {}
            prerequisites.append({
                "id": prerequisite,
                "name": prerequisite_tech.get("localised_name") or prerequisite,
                "num": order.get(prerequisite, 0),
            })

        craft_trigger = None
        if tech.get("craft_trigger"):
            try:
                trigger_count = int(tech.get("craft_trigger_count", 1) or 1)
            except (TypeError, ValueError):
                trigger_count = 1
            craft_trigger = {
                "name": tech["craft_trigger"],
                "count": max(trigger_count, 1),
            }

        out[tid] = {
            "id": tid,
            "name": tech.get("localised_name") or tid,
            "num": order.get(tid, 0),
            "free": tid in free,
            "count": count,
            "time": unit.get("time"),
            "ingredients": ingredients,
            "prerequisites": prerequisites,
            "craft_trigger": craft_trigger,
            "unlocks": unlocks,
        }
    return out


def _item_tech_info(seed: dict) -> dict[str, dict]:
    """Sciences ET tech(s) de déblocage de chaque item — ce que la SEED a
    assigné (pas le vanilla) : techs = ``seed['technologies']``, ordre =
    ``seed['progression_order']`` (numéro d'apparition 1..N).

    Les techs starter (``free_researches``) débloquent des recettes gratuites
    au démarrage : leurs items forment le groupe Starter (rank = 0). Un item
    peut être débloqué par PLUSIEURS techs : on les fusionne (l'item tombe
    dans le groupe de la tech la plus précoce) mais on GARDE toutes les techs
    dans le badge/la fiche ("num · nom + num · nom").

    Renvoie {item → {"rank": 0 si starter/aucune, sinon n° d'apparition de la
    première tech non-starter, "techs": [{"num": n, "name": …}] par numéro
    croissant, "tech": affichage "3 · nom + 5 · nom", "primaryTech": première,
    "science": packs requis, "scienceRank": science la plus haute}}."""
    tmap, order, free, rec_by_recipe = _tech_order(seed)
    tech_by_item: dict[str, set[tuple[int, str]]] = {}
    for tid, num in order.items():
        t = tmap[tid]
        for eff in t.get("effects") or []:
            if eff.get("type") != "unlock-recipe":
                continue
            for prod in rec_by_recipe.get(eff.get("recipe"), []):
                tech_by_item.setdefault(prod, set()).add((num, tid))

    def local(tid: str) -> str:
        return tmap[tid].get("localised_name") or tid

    def packs_of(tid: str) -> set[str]:
        return {
            ing.get("name")
            for ing in (tmap[tid].get("unit") or {}).get("ingredients") or []
            if str(ing.get("name", "")).endswith("-science-pack")
        }

    out: dict[str, dict] = {}
    for item, items in tech_by_item.items():
        items = sorted(items)
        reals = [(num, tid) for (num, tid) in items if tid not in free]
        rank = min(num for num, _ in reals) if reals else 0
        tech_list = [{"num": num, "name": local(tid)} for num, tid in items]
        display = " + ".join(f"{o['num']} · {o['name']}" for o in tech_list)
        all_packs: set[str] = set()
        for _, tid in items:
            all_packs |= packs_of(tid)
        non_start = sorted(
            (p for p in all_packs if p != "start"),
            key=lambda p: _SCIENCE_RANK.get(p, 99),
        )
        out[item] = {
            "rank": rank,
            "techs": tech_list,
            "tech": display,
            "primaryTech": tech_list[0]["name"] if tech_list else "",
            "science": " + ".join(p.replace("-science-pack", "") for p in non_start) or "aucune",
            "scienceRank": max((_SCIENCE_RANK.get(p, 0) for p in all_packs), default=0),
        }
    return out


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
    raw_sources = _seed_raw_sources(seed)

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

    # Les ressources brutes de la seed (patches, environnementaux bois/pierre/
    # poisson, fluides d'extraction) sont TOUJOURS des nœuds « source », même
    # si aucune recette ne les consomme (une matière jamais consommée ne doit
    # pas devenir invisible) : §6, `raw_sources` = pool.brutes de la seed.
    nodes |= raw_sources

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
    info, recips = _node_info(seed)
    techs = _technology_info(seed)
    title = f"randputF seed {seed.get('meta', {}).get('seed', '?')}"
    path.write_text(
        _HTML_TEMPLATE.replace("__TITLE__", title)
        .replace("__SVG__", svg)
        .replace("__INFO__", json.dumps(info))
        .replace("__RECIPS__", json.dumps(recips))
        .replace("__TECHS__", json.dumps(techs)),
        encoding="utf-8",
    )


def _seed_raw_sources(seed: dict) -> set[str]:
    """Ressources brutes assignées par la SEED (docs/model.md §3, §5 — ce que le mod
    extrait sur la carte) : le pool ``raw_resources`` du seed (= patches posés
    au sol + environnementaux + fluides d'extraction, généré par
    ``db.raw_resources``) complété par les environnementaux vanilla."""
    return set(ENVIRONMENTAL_ITEMS) | set((seed.get("pools") or {}).get("raw_resources") or ())


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


def _node_info(seed: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Fiche de chaque nœud pour l'interface : voisins (ingrédients / produits
    qui l'utilisent), tech(s) de déblocage et icône embarquée en data-URI.
    Renvoie aussi RECIPS : une entrée par RECETTE (produit, ingrédients, tech,
    rang, brut, icône) pour le panneau « une ligne par recette »."""
    info: dict[str, dict] = {}
    for recipe in seed.get("recipes") or []:
        products = [res["name"] for res in (recipe.get("results") or [])]
        ingredients = [ing["name"] for ing in (recipe.get("ingredients") or [])]
        for p in products:
            for ing in ingredients:
                info.setdefault(p, {}).setdefault("ingredients", []).append(ing)
                info.setdefault(ing, {}).setdefault("used_by", []).append(p)
    tinfo = _item_tech_info(seed)
    retech = _recipe_tech_info(seed)
    resources = _seed_raw_sources(seed)
    icons: dict[str, str | None] = {}

    def icon_uri(name: str) -> str | None:
        if name not in icons:
            icon = _icon_path(name)
            if icon is None:
                icons[name] = None
            else:
                try:
                    icons[name] = "data:image/png;base64," + base64.b64encode(crop_mip(icon.read_bytes())).decode()
                except OSError:
                    icons[name] = None
        return icons[name]

    # recettes DISTINCTES produisant chaque item (dégoupillonné), pour le
    # sélecteur « autre recette » de la fiche (items multi-recettes)
    prod_recipes: dict[str, list[dict]] = {}
    for recipe in seed.get("recipes") or []:
        ing = sorted(
            (i["name"], int(i.get("amount", 1)))
            for i in (recipe.get("ingredients") or [])
        )
        for res in recipe.get("results") or []:
            p = res["name"]
            lst = prod_recipes.setdefault(p, [])
            if all(existing["items"] != ing for existing in lst):
                lst.append({"id": recipe.get("name", ""), "items": ing})
    for name, rec in info.items():
        t = tinfo.get(name)
        rec["raw"] = name in resources
        rec["rank"] = t["rank"] if t else 0
        rec["techs"] = t["techs"] if t else []
        rec["tech"] = t["tech"] if t else ""
        rec["primaryTech"] = t["primaryTech"] if t else ""
        rec["science"] = t["science"] if t else ""
        rec["scienceRank"] = t["scienceRank"] if t else 0
        multirecipes = prod_recipes.get(name) or []
        if len(multirecipes) > 1:
            rec["recipes"] = multirecipes
        if icon_uri(name):
            rec["icon"] = icon_uri(name)
    recips: dict[str, dict] = {}
    for recipe in seed.get("recipes") or []:
        rid = recipe.get("name", "")
        res = recipe.get("results") or []
        if not res:
            continue
        p = res[0]["name"]
        ings = [
            [i.get("name", ""), int(i.get("amount", 1))]
            for i in (recipe.get("ingredients") or [])
        ]
        t = retech.get(rid) or {}
        recips[rid] = {
            "p": p,
            "i": ings,
            "num": t.get("num", 0),
            "name": t.get("name", ""),
            "tech": t.get("tech", ""),
            "techs": t.get("techs", []),
            "raw": p in resources,
            "icon": icon_uri(p),
        }
    return info, recips


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
  #sidebar { position:absolute; left:0; top:0; bottom:0; width:var(--sidebarw,450px); z-index:7;
    display:flex; flex-direction:column; background:var(--panel);
    border-right:1px solid var(--line); }
  #sidegrip { position:absolute; left:var(--sidebarw,450px); top:0; bottom:0; width:6px;
    z-index:8; cursor:col-resize; touch-action:none; }
  #sidegrip:hover, #sidegrip.active { background:rgba(111,111,230,.35); }
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
    cursor:pointer; font-size:12px; border-left:4px solid transparent; }
  .row:hover { background:rgba(255,255,255,.07); }
  .row.dim { opacity:.25; }
  .row img { width:30px; height:30px; flex:none; image-rendering:pixelated;
    object-fit:contain; object-position:center; }
  .row .col { flex:1; min-width:0; display:flex; flex-direction:column; gap:1px; }
  .row .nn { white-space:normal; word-break:break-word; overflow-wrap:anywhere; }
  .row .sub { font-size:10px; color:var(--muted); white-space:normal; word-break:break-word; overflow-wrap:anywhere; }
  .row .sc { margin-left:auto; flex:none; font-size:10px; color:var(--muted); font-weight:700; }
  .techlink { appearance:none; border:0; padding:0; background:transparent; color:inherit;
    cursor:pointer; font:inherit; font-size:inherit; font-weight:inherit; line-height:inherit;
    display:inline; vertical-align:baseline; text-align:left; }
  .techlink:hover, .techlink.selected { color:#aeb0ff; text-decoration:underline; }
  .grp.techgroup { appearance:none; border:0; padding:0; background:transparent; color:var(--muted);
    cursor:pointer; display:block; width:100%; font-size:10px; text-transform:uppercase;
    letter-spacing:.05em; font-weight:700; text-align:left; }
  .grp.techgroup:hover, .grp.techgroup.selected { color:#aeb0ff; }
  .grp.techgroup.selected { background:rgba(111,111,230,.12); }
  /* ---- viewer ---- */
  #viewer { position:absolute; top:0; right:0; bottom:0; left:var(--sidebarw,450px); }
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
  #panel { top:58px; right:10px; width:min(380px, calc(100vw - 20px)); padding:16px; display:none;
    font-size:13px; max-height:calc(100% - 86px); overflow-y:auto; }
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
  #panel .tech-id { color:var(--muted); font-size:10px; margin-bottom:9px; overflow-wrap:anywhere; }
  #panel .tech-summary { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px; margin:8px 0 4px; }
  #panel .tech-stat { min-width:0; padding:6px 8px; border:1px solid var(--line);
    border-radius:7px; background:rgba(255,255,255,.04); }
  #panel .tech-stat label { display:block; color:var(--muted); font-size:9px;
    text-transform:uppercase; letter-spacing:.06em; }
  #panel .tech-stat strong { display:block; margin-top:2px; font-size:12px; overflow-wrap:anywhere; }
  #panel .tech-trigger { margin:8px 0 0; padding:8px; border:1px solid var(--line);
    border-radius:7px; background:rgba(255,255,255,.04); }
  #panel .tech-trigger-title { color:var(--muted); font-size:10px; text-transform:uppercase;
    letter-spacing:.06em; margin-bottom:4px; }
  #panel .tech-trigger-note { color:var(--txt); font-size:12px; line-height:1.4; }
  #panel .tech-list { margin:8px 0 0; }
  #panel .tech-list li { display:flex; align-items:center; gap:6px; min-width:0; }
  #panel .tech-list img { width:22px; height:22px; float:none; margin:0; border:0; border-radius:3px; }
  #panel .tech-list .label { flex:1; min-width:0; overflow-wrap:anywhere; }
  #panel .tech-list .amount { margin-left:auto; color:var(--muted); font-variant-numeric:tabular-nums;
    white-space:nowrap; }
  #panel .tech-list .per-unit { color:var(--muted); font-size:10px; white-space:nowrap; }
  #panel .tech-list .recipe { color:var(--muted); font-size:10px; overflow-wrap:anywhere; }
  #panel .tech-list .panel-tech { flex:1; min-width:0; border:0; padding:0; background:transparent;
    color:var(--txt); font:inherit; text-align:left; cursor:pointer; }
  #panel .tech-list .panel-tech:hover { color:#aeb0ff; text-decoration:underline; }
  #panel .tech-list .tech-empty { display:block; color:var(--muted); font-size:12px; }
  #panel .rcp { display:flex; align-items:center; gap:6px; margin:2px 0 10px; padding:5px 9px;
    font-size:12px; color:var(--txt); background:rgba(255,255,255,.05); border:1px dashed var(--line);
    border-radius:6px; cursor:pointer; }
  #panel .rcp:hover { background:rgba(255,255,255,.12); }
  #panel .rcp .arr { color:var(--accent,#fe7b21); font-weight:800; }
  #panel .rcp .cnt { margin-left:auto; color:var(--muted); font-variant-numeric:tabular-nums; }
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
<div id="sidegrip"></div>
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
const RECIPS = __RECIPS__;
const TECHS = __TECHS__;
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
let sortMode = 'science', lastSel = null, lastTech = null, selBig = null, subOnly = false, ficheRecipeIndex = 0;
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
  /* quand la fenêtre change de taille, seul le mini-graphe se ré-ajuste.
     Le grand graphe est VERROUILLÉ sur son zoom + sa position courants : un
     redimensionnement ne doit pas le déplacer (rebranche la vue d'ensemble
     uniquement par double-clic). */
  function refitActive() {
    if (minigraph.style.display === 'block') miniFit();
  }
  addEventListener('resize', refitActive);
  /* ---- redimensionnement du panneau latéral (poignée) ---- */
  const sidegrip = document.getElementById('sidegrip');
  const rootStyle = () => (document.documentElement || document.body).style;
  const setSidebarW = w => {
    const v = w + 'px';
    const st = rootStyle();
    if (st.setProperty) st.setProperty('--sidebarw', v); else st['--sidebarw'] = v;
  };
  const clampW = w => {
    if (!isFinite(w)) w = 450;
    return Math.max(180, Math.min(w, Math.max(180, innerWidth - 280)));
  };
  let savedW = null;
  try { savedW = localStorage.getItem('randputf-sidebarw'); } catch (e) {}
  if (savedW) setSidebarW(clampW(parseFloat(savedW)));
  let sideDrag = false, curW = 450;
  sidegrip.addEventListener('pointerdown', e => {
    sideDrag = true; curW = clampW(e.clientX);
    sidegrip.classList.add('active');
    if (sidegrip.setPointerCapture) sidegrip.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  addEventListener('pointermove', e => {
    if (!sideDrag) return;
    curW = clampW(e.clientX); setSidebarW(curW);
  });
  addEventListener('pointerup', () => {
    if (!sideDrag) return;
    sideDrag = false; sidegrip.classList.remove('active');
    if (minigraph.style.display === 'block') miniFit();
    try { localStorage.setItem('randputf-sidebarw', String(Math.round(curW))); } catch (e) {}
  });
  fit();
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
      // chaque panneau flottant masque la zone visible sur le bord du viewer
      // auquel il est le plus proche (fiche/sous-graphe à droite, profondeur en
      // bas, thème à gauche). Un petit bouton au milieu ne doit pas faire
      // disparaître tout un bord : on ne retient que sa place sur CET bord.
      const dl = rl - vr.left, dr = vr.left + vw - right, dt = rt - vr.top, db = vr.top + vh - bottom;
      const minD = Math.min(dl, dr, dt, db);
      if (minD === dl) leftIn = Math.max(leftIn, Math.min(vw, Math.max(0, right - vr.left)));
      else if (minD === dr) rightIn = Math.max(rightIn, Math.min(vw, Math.max(0, vr.left + vw - rl)));
      else if (minD === dt) topIn = Math.max(topIn, Math.min(vh, Math.max(0, bottom - vr.top)));
      else botIn = Math.max(botIn, Math.min(vh, Math.max(0, vr.top + vh - rt)));
    }
    const availW = Math.max(20, vw - leftIn - rightIn);
    const availH = Math.max(20, vh - topIn - botIn);
    miniK = Math.max(0.05, Math.min(1, Math.min((availW - 24) / w, (availH - 24) / h)));
    miniTX = leftIn + (availW - w * miniK) / 2;
    miniTY = topIn + (availH - h * miniK) / 2;
    miniSvgApply();
  }
  /* ---- téléportation (pan) du grand graphe sur l'élément sélectionné,
         SANS changer le zoom : la vue glisse pour centrer le nœud ---- */
  function tpTo(name) {
    const g = nodeEls[name];
    if (!g || subOnly) return;
    const r = g.getBoundingClientRect();
    const vv = viewer.getBoundingClientRect();
    if (!r || r.width <= 0 || r.height <= 0 || !vv || vv.width <= 1) return;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    tx += (vv.left + vv.width / 2) - cx;
    ty += (vv.top + vv.height / 2) - cy;
    apply();
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
  /* cascade en miroir dans le panneau (une ligne par RECETTE) : la ligne est
     grisée si son PRODUIT n'est pas dans la cascade, sinon colorée par niveau. */
  function applyRowDim(name, depth) {
    for (const rid of Object.keys(rowEls)) {
      const r = rowEls[rid]; const prod = (RECIPS[rid] || {}).p || rid;
      if (depth[prod] === undefined) { r.classList.add('dim'); lastRows.push(r); }
      else { r.classList.remove('dim'); r.style.borderLeftColor = prod === name ? focusCol() : colorOf(depth[prod]); lastRows.push(r); }
    }
  }
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
      // ressource BRUTE = terminal de détection : ses ingrédients ne sont pas
      // explorés (elle peut avoir un craft, ce n'est pas une vraie source).
      if ((INFO[cur] || {}).raw) continue;
      // l'élément sélectionné (avec plusieurs recettes) développe la cascade
      // selon la recette COURANTE du sélecteur ; les autres utilisent tout.
      const ings = (cur === name) ? ingredientsOf(name)
        : (INFO[cur] || {}).ingredients || [];
      for (const x of ings) {
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
    applyRowDim(name, depth);
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
    ficheRecipeIndex = 0;
    renderFiche(name);
  }
  function renderFiche(name) {
    fiche.innerHTML = '';
    const img = nodeEls[name] && nodeEls[name].querySelector('image');
    if (img) {
      const i = document.createElement('img');
      i.src = img.getAttribute('xlink:href') || img.getAttribute('href');
      fiche.appendChild(i);
    }
    const h = document.createElement('h3'); h.textContent = name; fiche.appendChild(h);
    const info = INFO[name] || {};
    if (info.tech) {
      const d = document.createElement('div'); d.className = 'sci';
      d.textContent = 'Débloqué par : ' + info.tech;
      fiche.appendChild(d);
    }
    const mk = (label, list, noCount) => {
      if (!list || !list.length) return;
      const sep = document.createElement('div'); sep.className = 'sep'; sep.textContent = label + (noCount ? '' : ' (' + list.length + ')');
      fiche.appendChild(sep);
      const u = document.createElement('ul');
      const names = [];
      for (const e of list) {
        const n = typeof e === 'string' ? e : e.name;
        if (names.includes(n)) continue;
        names.push(n);
      }
      for (const n of names) {
        const e = list.find(x => (typeof x === 'string' ? x : x.name) === n);
        const li = document.createElement('li');
        li.textContent = (typeof e === 'string' || !e.amount || e.amount <= 1) ? n : n + ' × ' + e.amount;
        li.addEventListener('click', () => { selectPanel(n); });
        u.appendChild(li);
      }
      fiche.appendChild(u);
    };
    const recipes = info.recipes && info.recipes.length > 1 ? info.recipes : null;
    if (recipes) {
      const ri = ficheRecipeIndex % recipes.length;
      const rc = recipes[ri];
      const sw = document.createElement('div'); sw.className = 'rcp';
      const arr = document.createElement('b'); arr.className = 'arr'; arr.textContent = '\u25B8';
      sw.appendChild(arr);
      sw.appendChild(document.createTextNode(' autre recette'));
      const cnt = document.createElement('b'); cnt.className = 'cnt';
      cnt.textContent = (ri + 1) + '/' + recipes.length;
      sw.appendChild(cnt);
      sw.title = 'Recette suivante (' + rc.id + ')';
      sw.addEventListener('click', () => {
        ficheRecipeIndex = (ficheRecipeIndex + 1) % recipes.length;
        renderFiche(name);
        if (subOnly) buildMini(name); else highlight(name);
      });
      fiche.appendChild(sw);
      mk('Ingrédients — recette ' + (ri + 1) + '/' + recipes.length,
         rc.items.map(([n, a]) => ({ name: n, amount: a })), true);
      mk('Utilisé par', info.used_by);
    } else {
      mk('Ingrédients', info.ingredients);
      mk('Utilisé par', info.used_by);
    }
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
      // sélection (ligne, nœud, fiche) : on reste sur le grand graphe
      subcheck.checked = false; subOnly = false;
      removeMini();
      highlight(name);
    }
    lastSel = name;
    lastTech = null;
    updateTechSelection();
  }
  // clic sur un item du PANNEAU (liste, fiche) : si on est dans le sous-graphe,
  // on y reste (on navigue dedans) ; sinon on téléporte sur l'item dans le grand.
  function selectPanel(name) {
    if (subOnly) select(name, 'mini');
    else { select(name); tpTo(name); }
  }
  // clic sur une RECETTE du panneau : on sélectionne le produit en forçant le
  // sélecteur de recette de la fiche sur CETTE recette (les items produits par
  // plusieurs recettes affichent alors la bonne variante dans le graphe).
  function selectRecipe(rid) {
    const r = RECIPS[rid]; if (!r) return;
    const info = INFO[r.p] || {};
    if (info.recipes) {
      for (let k = 0; k < info.recipes.length; k++) {
        if (info.recipes[k].id === rid) { ficheRecipeIndex = k; break; }
      }
    }
    selectPanel(r.p);
  }
  function renderTechFiche(tech) {
    fiche.innerHTML = '';
    const h = document.createElement('h3');
    h.textContent = tech.name;
    fiche.appendChild(h);
    const id = document.createElement('div');
    id.className = 'tech-id';
    id.textContent = tech.id;
    fiche.appendChild(id);

    const count = Number(tech.count) || 1;
    const trigger = tech.craft_trigger;
    const summary = document.createElement('div');
    summary.className = 'tech-summary';
    const addStat = (label, value) => {
      const stat = document.createElement('div');
      stat.className = 'tech-stat';
      const key = document.createElement('label');
      key.textContent = label;
      const val = document.createElement('strong');
      val.textContent = value;
      stat.appendChild(key);
      stat.appendChild(val);
      summary.appendChild(stat);
    };
    addStat('Position', tech.free ? 'Démarrage' : '#' + tech.num);
    if (trigger) {
      addStat('Type', 'Alternative');
      addStat('Déblocage', 'Fabrication');
    } else if (tech.free) {
      addStat('Statut', 'Gratuite');
      addStat('Coût', 'Aucun');
    } else {
      addStat('Unités de recherche', count + (count > 1 ? ' unités' : ' unité'));
      const time = Number(tech.time);
      if (Number.isFinite(time) && time > 0) {
        addStat('Temps de base / unité', time + ' s');
        addStat('Temps de base total', (time * count) + ' s');
      }
    }
    fiche.appendChild(summary);

    const makeList = (label) => {
      const sep = document.createElement('div');
      sep.className = 'sep';
      sep.textContent = label;
      fiche.appendChild(sep);
      const list = document.createElement('ul');
      list.className = 'tech-list';
      return list;
    };
    const addItem = (list, label, amount, handler, recipe, icon, buttonLabel, perUnit) => {
      const li = document.createElement('li');
      if (icon) {
        const img = document.createElement('img');
        img.src = icon;
        li.appendChild(img);
      }
      const name = document.createElement(buttonLabel ? 'button' : 'span');
      if (buttonLabel) {
        name.type = 'button';
        name.className = 'panel-tech';
      } else {
        name.className = 'label';
      }
      name.textContent = label;
      li.appendChild(name);
      if (recipe) {
        const recipeName = document.createElement('span');
        recipeName.className = 'recipe';
        recipeName.textContent = recipe;
        li.appendChild(recipeName);
      }
      if (amount) {
        const amountEl = document.createElement('span');
        amountEl.className = 'amount';
        amountEl.textContent = amount;
        li.appendChild(amountEl);
      }
      if (perUnit) {
        const perUnitEl = document.createElement('span');
        perUnitEl.className = 'per-unit';
        perUnitEl.textContent = perUnit;
        li.appendChild(perUnitEl);
      }
      if (handler) li.addEventListener('click', handler);
      list.appendChild(li);
    };

    if (trigger) {
      const box = document.createElement('div');
      box.className = 'tech-trigger';
      const title = document.createElement('div');
      title.className = 'tech-trigger-title';
      title.textContent = 'Déclencheur de déblocage';
      const note = document.createElement('div');
      note.className = 'tech-trigger-note';
      note.textContent = 'Cette alternative se débloque après avoir crafté :';
      const list = document.createElement('ul');
      list.className = 'tech-list';
      const info = INFO[trigger.name] || {};
      addItem(list, trigger.name, '× ' + trigger.count, () => {
        selectPanel(trigger.name);
      }, null, info.icon, false);
      box.appendChild(title);
      box.appendChild(note);
      box.appendChild(list);
      fiche.appendChild(box);
    }

    const prerequisites = tech.prerequisites || [];
    if (prerequisites.length) {
      const list = makeList('Prérequis (' + prerequisites.length + ')');
      for (const prerequisite of prerequisites) {
        addItem(list, prerequisite.name, prerequisite.num ? '#' + prerequisite.num : null, () => {
          selectTech(prerequisite.id);
        }, null, null, true);
      }
      fiche.appendChild(list);
    }

    const ingredients = tech.ingredients || [];
    if (ingredients.length) {
      const list = makeList('Coût de recherche (' + ingredients.length + ')');
      for (const ingredient of ingredients) {
        const info = INFO[ingredient.name] || {};
        const perUnit = count > 1 ? '(' + (ingredient.amount / count) + '/u)' : null;
        addItem(list, ingredient.name, '× ' + ingredient.amount, () => {
          selectPanel(ingredient.name);
        }, null, info.icon, false, perUnit);
      }
      fiche.appendChild(list);
    } else if (!trigger) {
      const list = makeList('Coût de recherche');
      const empty = document.createElement('li');
      empty.className = 'tech-empty';
      empty.textContent = 'Aucun ingrédient requis.';
      list.appendChild(empty);
      fiche.appendChild(list);
    }

    const unlocks = tech.unlocks || [];
    if (unlocks.length) {
      const list = makeList('Débloque (' + unlocks.length + ')');
      for (const unlock of unlocks) {
        const recipe = RECIPS[unlock.recipe] || {};
        const product = unlock.product || recipe.p || unlock.recipe;
        addItem(list, product, null, () => {
          selectRecipe(unlock.recipe);
        }, unlock.recipe, recipe.icon, false);
      }
      fiche.appendChild(list);
    }
  }
  function selectTech(id) {
    const tech = TECHS[id];
    if (!tech) return;
    clearHigh();
    if (subOnly) {
      subOnly = false;
      subcheck.checked = false;
      removeMini();
    }
    lastSel = null;
    lastTech = id;
    updateTechSelection();
    selBig = null;
    hideSubOption();
    renderTechFiche(tech);
    panel.style.display = 'block';
  }
  function removeMini() {
    minigraph.style.display = 'none';
    minigraph.innerHTML = '';
    biggraph.style.display = '';
    miniReset();
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
  // Ingrédients de l'élément selon la recette sélectionnée dans la fiche :
  // pour un élément multi-recettes, la cascade affiche la recette COURANTE.
  function ingredientsOf(name) {
    const i = INFO[name] || {};
    const rs = i.recipes;
    if (rs && rs.length > 1) {
      const r = rs[ficheRecipeIndex % rs.length];
      return (r.items || []).map(x => x[0]);
    }
    return i.ingredients || [];
  }
  function buildMini(name) {
    clearHigh();
    const depth = {}; depth[name] = 0;
    const q = [name];
    while (q.length) {
      const cur = q.shift();
      // ressource BRUTE = terminal de détection (détection identique au grand
      // graphe) : ne jamais explorer ses ingrédients, même s'il a un craft.
      if ((INFO[cur] || {}).raw) continue;
      // l'élément sélectionné (avec plusieurs recettes) développe la cascade
      // selon la recette COURANTE du sélecteur ; les autres utilisent tout.
      const ings = (cur === name) ? ingredientsOf(name)
        : (INFO[cur] || {}).ingredients || [];
      for (const x of ings) {
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
    applyRowDim(name, depth);
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
    lastSel = null; lastTech = null; subcheck.checked = false; subOnly = false; hideSubOption();
    updateTechSelection();
  });
  subcheck.addEventListener('change', () => {
    if (subcheck.checked) {
      // petit graphe ouvert sur l'item du grand graphe : on enregistre l'ancre
      if (lastSel) { selBig = lastSel; select(lastSel, 'mini'); }
    } else {
      // retour petit → grand : téléport SANS changer le zoom si on a navigué
      // dans le petit vers un item différent de celui du grand (sinon : rien)
      subOnly = false;
      removeMini();
      if (lastSel) {
        highlight(lastSel);
        if (selBig !== null && selBig !== lastSel) tpTo(lastSel);
        selBig = lastSel;
      }
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
    if (lastTech) renderTechFiche(TECHS[lastTech]);
    else if (lastSel) { if (subOnly) buildMini(lastSel); else highlight(lastSel); }
  }
  themeBtn.addEventListener('click', () => setTheme(!document.body.classList.contains('day')));
  try { setTheme(localStorage.getItem('randputfTheme') === 'day'); } catch (e) { setTheme(false); }
  /* ---- panneau : recherche + tri + liste ---- */
  search.addEventListener('input', () => {
    clearHigh(); removeMini(); panel.style.display = 'none';
    lastSel = null; lastTech = null; subcheck.checked = false; subOnly = false; hideSubOption(); renderList();
  });
  addEventListener('keydown', e => { if (e.key === 'Escape') { search.value=''; search.dispatchEvent(new Event('input')); } });
  document.querySelectorAll('.sortbtn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.sortbtn').forEach(x => x.classList.toggle('active', x === b));
    sortMode = b.dataset.sort; renderList();
  }));
  function updateTechSelection() {
    list.querySelectorAll('[data-tech-id]').forEach(el => {
      el.classList.toggle('selected', !!lastTech && el.dataset.techId === lastTech);
    });
  }
  function renderList() {
    list.innerHTML = ''; rowEls = {};
    const q = search.value.trim().toLowerCase();
    let entries = Object.entries(RECIPS);
    if (q) entries = entries.filter(([rid, r]) => (r.p + ' ' + rid).toLowerCase().includes(q));
    const gkey = r => (r.raw ? -1 : (r.num > 0 ? r.num + 1 : 0));
    if (sortMode === 'science') {
      entries.sort((a,b) => gkey(a[1]) - gkey(b[1]) || a[1].p.localeCompare(b[1].p) || a[0].localeCompare(b[0]));
    } else {
      entries.sort((a,b) => a[1].p.localeCompare(b[1].p) || a[0].localeCompare(b[0]));
    }
    let grp = null;
    for (const [rid, r] of entries) {
      if (sortMode === 'science') {
        const g0 = gkey(r);
        if (g0 !== grp) {
          grp = g0;
          const techList = r.techs || [];
          const firstTech = techList.find(t => r.num > 0 ? t.num === r.num : t.free) || techList[0];
          if (g0 < 0) {
            const hd = document.createElement('div');
            hd.className = 'grp';
            hd.textContent = 'Ressources brutes (finies + infinies)';
            list.appendChild(hd);
          } else if (firstTech) {
            const hd = document.createElement('button');
            hd.type = 'button';
            hd.className = 'grp techgroup';
            hd.dataset.techId = firstTech.id;
            if (lastTech === firstTech.id) hd.classList.add('selected');
            hd.textContent = g0 === 0 ? 'Starter' : (g0 - 1) + ' · ' + (r.name || r.tech);
            hd.title = 'Voir le coût de ' + firstTech.name;
            hd.addEventListener('click', () => selectTech(firstTech.id));
            list.appendChild(hd);
          } else {
            const hd = document.createElement('div');
            hd.className = 'grp';
            hd.textContent = 'Starter';
            list.appendChild(hd);
          }
        }
      }
      const row = document.createElement('div'); row.className = 'row';
      if (r.icon) {
        const im = document.createElement('img'); im.src = r.icon; row.appendChild(im);
      }
      const col = document.createElement('div'); col.className = 'col';
      const sp = document.createElement('span'); sp.className = 'nn'; sp.textContent = r.p; col.appendChild(sp);
      if (r.i && r.i.length) {
        const su = document.createElement('span'); su.className = 'sub';
        su.textContent = r.i.map(x => (x[1] > 1 ? x[0] + ' ×' + x[1] : x[0])).join(' · ');
        col.appendChild(su);
      }
      row.appendChild(col);
      row.addEventListener('click', () => selectRecipe(rid));
      rowEls[rid] = row; list.appendChild(row);
    }
    if (!entries.length) {
      const e = document.createElement('div'); e.className = 'grp'; e.textContent = 'aucun résultat';
      list.appendChild(e);
    }
    updateTechSelection();
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