"""Export du graphe de difficulté comparé : baseline vanilla vs seed.

Le dump vanilla (``data/vanilla_dump.json``, produit par le mod compagnon
``exporter/``) fournit recettes ET technologies. On en tire une « seed »
factice au même schéma que la seed générée, puis on réutilise telle quelle
l'ardoise de difficulté (``tool.audit.difficulty``) : aucun calcul dupliqué.

Sortie ``seed.difficulty.html`` : SVG autonome (aucune dépendance externe) —
courbe du coût brut cumulé au fil de la progression, vanilla vs mod, plus un
tableau par tech (coût cumulé et items débloqués = « items à crafter »).
"""

from __future__ import annotations

import html
from pathlib import Path

from tool.audit.difficulty import difficulty_series
from tool.parsers.vanilla import load_db_from_dump

# Gisements bruts de vanilla (l'outil ne pose aucun patch ici : ce sont les
# ressources extraites du sol du jeu de base ; les fluides d'extraction —
# eau, pétrole brut — et l'environnement sont ajoutés par la base).
VANILLA_ORES = frozenset({"iron-ore", "copper-ore", "coal", "stone", "uranium-ore"})

_MOD_COLOR = "#e8734a"
_VANILLA_COLOR = "#5aa9e6"


def vanilla_seed_from_dump(dump: dict) -> dict | None:
    """Convertit le dump vanilla en « seed » au schéma de l'outil.

    Renvoie ``None`` si le dump n'embarque pas les technologies (dump régénéré
    avant l'ajout de ``dump_technologies`` : relancer l'exporter)."""
    technologies_raw = dump.get("technologies")
    if not technologies_raw:
        return None

    recipes = [
        {
            "name": name,
            "ingredients": recipe.get("ingredients") or [],
            "results": recipe.get("products") or [],
        }
        for name, recipe in (dump.get("recipes") or {}).items()
    ]
    technologies = [
        {
            "id": name,
            "localised_name": name,
            "prerequisites": tech.get("prerequisites") or [],
            "unit": tech.get("unit") or {},
            "effects": tech.get("effects") or [],
        }
        for name, tech in technologies_raw.items()
    ]

    # Ressources brutes : mêmes règles que pour une seed (patches + environnement
    # + fluides d'extraction), via la base parsée — aucune liste en dur ici.
    db = load_db_from_dump(dump)
    raw = sorted(db.raw_resources(set(VANILLA_ORES)))

    return {
        "meta": {"seed": 0},
        "pools": {"raw_resources": raw},
        "recipes": recipes,
        "technologies": technologies,
        "progression_order": [],
        "free_researches": [],
    }


def _fmt(value: float) -> str:
    """Nombre lisible : entier avec séparateurs d'espace (1 234 567)."""
    return f"{value:,.0f}".replace(",", "\u202f")


def _polyline(series: list[dict], x0, y0, x1, y1, max_n: int, max_y: float) -> str:
    if not series:
        return ""
    span_x = max(max_n - 1, 1)
    span_y = max(max_y, 1.0)
    pts = []
    for point in series:
        x = x0 + (point["num"] - 1) / span_x * (x1 - x0)
        y = y1 - (point["cumulative_total"] / span_y) * (y1 - y0)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _chart_svg(
    vanilla: list[dict], mod: list[dict],
    vanilla_label: str, mod_label: str,
) -> str:
    """SVG de la courbe cumulée, deux profils superposés."""
    x0, y0, x1, y1 = 80, 50, 1060, 470
    max_n = max(len(vanilla), len(mod), 1)
    max_y = max(
        (s[-1]["cumulative_total"] if s else 0.0) for s in (vanilla, mod)
    ) or 1.0

    parts: list[str] = []
    # Grille horizontale + graduations Y.
    for step in range(6):
        frac = step / 5
        y = y1 - frac * (y1 - y0)
        value = max_y * frac
        parts.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
            f'stroke="#33333d" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x0 - 10}" y="{y + 4:.1f}" fill="#8a8a99" '
            f'font-size="12" text-anchor="end">{html.escape(_fmt(value))}</text>'
        )
    # Axes.
    parts.append(
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#5a5a6b" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#5a5a6b" stroke-width="1.5"/>'
    )
    # Graduations X (indices de tech).
    for step in range(6):
        frac = step / 5
        x = x0 + frac * (x1 - x0)
        n = round(frac * (max_n - 1)) + 1
        parts.append(
            f'<text x="{x:.1f}" y="{y1 + 20}" fill="#8a8a99" font-size="12" '
            f'text-anchor="middle">{n}</text>'
        )

    parts.append(
        f'<polyline points="{_polyline(vanilla, x0, y0, x1, y1, max_n, max_y)}" '
        f'fill="none" stroke="{_VANILLA_COLOR}" stroke-width="2.5"/>'
    )
    parts.append(
        f'<polyline points="{_polyline(mod, x0, y0, x1, y1, max_n, max_y)}" '
        f'fill="none" stroke="{_MOD_COLOR}" stroke-width="2.5"/>'
    )

    # Légende.
    parts.append(f'<rect x="{x0}" y="14" width="14" height="14" fill="{_VANILLA_COLOR}"/>')
    parts.append(f'<text x="{x0 + 22}" y="26" fill="#d8d8e0" font-size="14">{html.escape(vanilla_label)}</text>')
    parts.append(f'<rect x="{x0 + 150}" y="14" width="14" height="14" fill="{_MOD_COLOR}"/>')
    parts.append(f'<text x="{x0 + 172}" y="26" fill="#d8d8e0" font-size="14">{html.escape(mod_label)}</text>')
    # Libellés d'axes.
    parts.append(f'<text x="{(x0 + x1) / 2:.0f}" y="{y1 + 46}" fill="#8a8a99" font-size="13" text-anchor="middle">tech (ordre de progression)</text>')
    parts.append(
        f'<text x="24" y="{(y0 + y1) / 2:.0f}" fill="#8a8a99" font-size="13" '
        f'text-anchor="middle" transform="rotate(-90 24 {(y0 + y1) / 2:.0f})">'
        f'ressources brutes cumulées</text>'
    )
    return f'<svg viewBox="0 0 1100 520" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'


def _table(series: list[dict], label: str, color: str) -> str:
    rows = []
    for point in series:
        products = ", ".join(point.get("products") or [])
        rows.append(
            "<tr>"
            f'<td class="n">{point["num"]}</td>'
            f'<td>{html.escape(point["name"])}</td>'
            f'<td class="num">{len(point.get("products") or [])}</td>'
            f'<td class="num">{html.escape(_fmt(point["cumulative_total"]))}</td>'
            f'<td class="prod">{html.escape(products)}</td>'
            "</tr>"
        )
    return (
        f'<div class="col"><h2 style="color:{color}">{html.escape(label)}</h2>'
        '<table><thead><tr><th>#</th><th>tech</th><th>items</th>'
        '<th>cumul brut</th><th>items à crafter (débloqués)</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>randputF — difficulté comparée</title>
<style>
  :root {{ --bg:#141419; --fg:#d8d8e0; --dim:#8a8a99; --line:#33333d; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
         font-family:system-ui,-apple-system,"Segoe UI",sans-serif; padding:24px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .sub {{ color:var(--dim); margin:0 0 18px; }}
  .totals {{ display:flex; gap:24px; flex-wrap:wrap; margin:0 0 18px; }}
  .tot {{ background:#1d1d24; border:1px solid var(--line); border-radius:8px;
          padding:10px 16px; }}
  .tot b {{ font-size:20px; }}
  .chart {{ background:#1a1a20; border:1px solid var(--line); border-radius:8px;
            padding:8px; margin-bottom:22px; }}
  svg {{ width:100%; height:auto; display:block; }}
  .cols {{ display:flex; gap:20px; align-items:flex-start; flex-wrap:wrap; }}
  .col {{ flex:1 1 480px; min-width:420px; }}
  h2 {{ font-size:16px; margin:6px 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; }}
  th,td {{ border-bottom:1px solid var(--line); padding:4px 6px; text-align:left;
           vertical-align:top; }}
  th {{ color:var(--dim); position:sticky; top:0; background:var(--bg); }}
  td.n {{ color:var(--dim); text-align:right; width:34px; }}
  td.num {{ text-align:right; white-space:nowrap; }}
  td.prod {{ color:var(--dim); font-size:11px; }}
</style>
</head>
<body>
<h1>randputF — difficulté comparée</h1>
<p class="sub">Coût en ressources brutes cumulé, tech par tech (la chaîne de la
fusée ferme chaque profil).</p>
<div class="totals">
  <div class="tot">vanilla<br><b style="color:{vanilla_color}">{vanilla_total}</b></div>
  <div class="tot">seed (mod)<br><b style="color:{mod_color}">{mod_total}</b></div>
  <div class="tot">rapport mod/vanilla<br><b>×{ratio:.2f}</b></div>
</div>
<div class="chart">{svg}</div>
<div class="cols">{tables}</div>
</body>
</html>
"""


def write_difficulty_graph_html(
    mod_seed: dict,
    vanilla_seed: dict,
    path: Path,
    *,
    mod_label: str = "seed (mod)",
    vanilla_label: str = "vanilla",
) -> Path:
    """Écrit le HTML comparatif. Lève ``ValueError`` si pas de séries."""
    vanilla_series = difficulty_series(vanilla_seed)
    mod_series = difficulty_series(mod_seed)
    if not vanilla_series or not mod_series:
        raise ValueError("série de difficulté vide")

    vanilla_total = vanilla_series[-1]["cumulative_total"]
    mod_total = mod_series[-1]["cumulative_total"]
    ratio = (mod_total / vanilla_total) if vanilla_total else 0.0

    doc = _TEMPLATE.format(
        vanilla_color=_VANILLA_COLOR,
        mod_color=_MOD_COLOR,
        vanilla_total=html.escape(_fmt(vanilla_total)),
        mod_total=html.escape(_fmt(mod_total)),
        ratio=ratio,
        svg=_chart_svg(vanilla_series, mod_series, vanilla_label, mod_label),
        tables=_table(vanilla_series, vanilla_label, _VANILLA_COLOR)
        + _table(mod_series, mod_label, _MOD_COLOR),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path
