"""Export du graphe de difficulté comparé : baseline vanilla vs seed.

Le dump vanilla (``data/vanilla_dump.json``, produit par le mod compagnon
``exporter/``) fournit recettes ET technologies. On en tire une « seed »
factice au même schéma que la seed générée, puis on réutilise telle quelle
l'ardoise de difficulté (``tool.audit.difficulty``) : aucun calcul dupliqué.

Sortie ``seed.difficulty.html`` : document autonome (aucune dépendance
externe) — courbe du coût brut cumulé au fil de la progression, vanilla vs mod.
Le graphe est **interactif** : survoler une tech affiche un repère vertical et
une infobulle (nom de la tech, coût propre, coût cumulé, items débloqués) pour
les deux séries à la fois ; un clic épingle l'infobulle ; les entrées de la
légende masquent/affichent une série ; cliquer une ligne du tableau met le
point correspondant en évidence.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from tool.audit.difficulty import difficulty_series
from tool.parsers.vanilla import load_db_from_dump

# Gisements bruts de vanilla (l'outil ne pose aucun patch ici : ce sont les
# ressources extraites du sol du jeu de base ; les fluides d'extraction —
# eau, pétrole brut — et l'environnement sont ajoutés par la base).
VANILLA_ORES = frozenset({"iron-ore", "copper-ore", "coal", "stone", "uranium-ore"})

_MOD_COLOR = "#e8734a"
_VANILLA_COLOR = "#5aa9e6"

# Géométrie du graphe (unités du viewBox ; le SVG est mis à l'échelle en CSS).
_SVG_W = 1100
_SVG_H = 540
_PAD_L = 66
_PAD_R = 22
_PAD_T = 18
_PAD_B = 56


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
        "technologies": technologies,
        "recipes": recipes,
        "progression_order": [],
        "pools": {"raw_resources": raw},
    }


def _fmt(value: float) -> str:
    """Format court pour les axes : séparateurs de milliers, sans décimale."""
    return f"{value:,.0f}".replace(",", "\u202f")


def _point_dict(point: dict) -> dict:
    products = point.get("products") or []
    return {
        "name": point.get("name") or point.get("id") or "",
        "raw": point.get("raw_total", 0.0),
        "cum": point.get("cumulative_total", 0.0),
        "products": products,
    }


def _chart_svg(
    vanilla_series: list[dict],
    mod_series: list[dict],
    vanilla_label: str,
    mod_label: str,
    vanilla_color: str,
    mod_color: str,
) -> tuple[str, str]:
    """Construit le SVG interactif + les données JSON injectées dans le HTML.

    Renvoie ``(svg, data_json)``. ``data_json`` décrit, pour chaque indice de
    tech, les deux points (mod et vanilla) afin que le JS affiche l'infobulle
    sans recalculer la géométrie."""
    max_n = max(len(vanilla_series), len(mod_series))
    if max_n == 0:
        return "", "{}"
    max_y = max(
        vanilla_series[-1]["cumulative_total"] if vanilla_series else 0.0,
        mod_series[-1]["cumulative_total"] if mod_series else 0.0,
        1.0,
    )

    x0, x1 = _PAD_L, _SVG_W - _PAD_R
    y0, y1 = _PAD_T, _SVG_H - _PAD_B
    span_x = (x1 - x0)

    def x_at(index: int) -> float:
        if max_n == 1:
            return (x0 + x1) / 2
        return x0 + index / (max_n - 1) * span_x

    def y_at(cum: float) -> float:
        return y1 - (cum / max_y) * (y1 - y0)

    parts: list[str] = [f'<svg id="diffsvg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
                        f'xmlns="http://www.w3.org/2000/svg" role="img">']

    # Grille horizontale + valeurs de l'axe Y.
    for step in range(6):
        frac = step / 5
        y = y1 - frac * (y1 - y0)
        parts.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
            f'stroke="#2b2b34" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x0 - 10}" y="{y + 4:.1f}" fill="#8a8a99" '
            f'font-size="12" text-anchor="end">{html.escape(_fmt(max_y * frac))}</text>'
        )
    # Axes.
    parts.append(
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#5a5a6b" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#5a5a6b" stroke-width="1.5"/>'
    )
    # Graduations X (numéro de tech), réparties en 8 repères.
    steps_x = min(8, max_n)
    for s in range(steps_x):
        frac = s / (steps_x - 1) if steps_x > 1 else 0.0
        idx = round(frac * (max_n - 1))
        x = x_at(idx)
        parts.append(
            f'<text x="{x:.1f}" y="{y1 + 20}" fill="#8a8a99" font-size="12" '
            f'text-anchor="middle">{idx + 1}</text>'
        )
    parts.append(
        f'<text x="{(x0 + x1) / 2:.0f}" y="{y1 + 42}" fill="#8a8a99" '
        f'font-size="13" text-anchor="middle">tech (ordre de progression)</text>'
    )
    parts.append(
        f'<text x="20" y="{(y0 + y1) / 2:.0f}" fill="#8a8a99" font-size="13" '
        f'text-anchor="middle" transform="rotate(-90 20 {(y0 + y1) / 2:.0f})">'
        f'ressources brutes cumulées</text>'
    )

    # Repère vertical (caché par défaut).
    parts.append(
        f'<line id="guide" class="guide" x1="{x0}" y1="{y0}" x2="{x0}" '
        f'y2="{y1}" style="display:none"/>'
    )

    # Courbes + points, une série par couleur.
    for series, color, cls in (
        (vanilla_series, vanilla_color, "v"),
        (mod_series, mod_color, "m"),
    ):
        if not series:
            continue
        coords = [(x_at(p["num"] - 1), y_at(p["cumulative_total"])) for p in series]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        parts.append(
            f'<polyline class="series {cls}" points="{poly}" fill="none" '
            f'stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
        )
        for (x, y), p in zip(coords, series):
            idx = p["num"] - 1
            parts.append(
                f'<circle class="pt {cls}" data-i="{idx}" cx="{x:.1f}" cy="{y:.1f}" '
                f'r="3.5" fill="{color}" stroke="#141419" stroke-width="1"/>'
            )

    # Zones de survol : une par indice, au-dessus de tout.
    slot = span_x / (max_n - 1) if max_n > 1 else span_x
    for idx in range(max_n):
        x = x_at(idx)
        left = max(x0, x - slot / 2)
        right = min(x1, x + slot / 2)
        parts.append(
            f'<rect class="hit" data-i="{idx}" x="{left:.1f}" y="{y0}" '
            f'width="{max(1.0, right - left):.1f}" height="{y1 - y0}" '
            f'fill="transparent"/>'
        )
    parts.append("</svg>")

    # Données injectées (infobulle sans recalcul de géométrie).
    v_by_idx = {p["num"] - 1: p for p in vanilla_series}
    m_by_idx = {p["num"] - 1: p for p in mod_series}
    records = []
    for idx in range(max_n):
        v = v_by_idx.get(idx)
        m = m_by_idx.get(idx)
        records.append(
            {
                "i": idx,
                "x": x_at(idx),
                "v": _point_dict(v) if v else None,
                "m": _point_dict(m) if m else None,
            }
        )
    data = {
        "points": records,
        "svh": _SVG_H,
        "svw": _SVG_W,
        "labels": {"v": vanilla_label, "m": mod_label},
        "colors": {"v": vanilla_color, "m": mod_color},
    }
    return "".join(parts), json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _table(series: list[dict], label: str, color: str, cls: str) -> str:
    rows = []
    for point in series:
        products = ", ".join(point.get("products") or [])
        rows.append(
            f'<tr class="trow {cls}" data-i="{point["num"] - 1}">'
            f'<td class="n">{point["num"]}</td>'
            f'<td>{html.escape(point["name"])}</td>'
            f'<td class="num">{len(point.get("products") or [])}</td>'
            f'<td class="num">{html.escape(_fmt(point.get("raw_total", 0.0)))}</td>'
            f'<td class="num">{html.escape(_fmt(point["cumulative_total"]))}</td>'
            f'<td class="prod">{html.escape(products)}</td>'
            "</tr>"
        )
    return (
        f'<div class="col"><h2 style="color:{color}">{html.escape(label)}</h2>'
        '<table><thead><tr><th>#</th><th>tech</th><th>items</th>'
        '<th>coût</th><th>cumul</th><th>items à crafter (débloqués)</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>randputF — difficulté comparée</title>
<style>
  :root {{ --bg:#141419; --fg:#d8d8e0; --dim:#8a8a99; --line:#33333d; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
         font-family:system-ui,-apple-system,"Segoe UI",sans-serif; padding:24px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .sub {{ color:var(--dim); margin:0 0 18px; }}
  .totals {{ display:flex; gap:24px; flex-wrap:wrap; margin:0 0 14px; }}
  .tot {{ background:#1d1d24; border:1px solid var(--line); border-radius:8px;
          padding:10px 16px; }}
  .tot b {{ font-size:20px; }}
  .legend {{ display:flex; gap:20px; flex-wrap:wrap; margin:0 0 10px; }}
  .legend span {{ cursor:pointer; user-select:none; display:inline-flex;
                  align-items:center; gap:7px; padding:3px 10px;
                  border:1px solid var(--line); border-radius:999px; font-size:13px; }}
  .legend span.off {{ opacity:.38; }}
  .legend i {{ width:11px; height:11px; border-radius:50%; display:inline-block; }}
  .chart {{ position:relative; background:#1a1a20; border:1px solid var(--line);
            border-radius:8px; padding:8px; margin-bottom:22px; }}
  svg {{ width:100%; height:auto; display:block; touch-action:none; }}
  .guide {{ stroke:#8a8a99; stroke-width:1; stroke-dasharray:4 4; pointer-events:none; }}
  circle.pt {{ transition:r .08s ease; }}
  circle.pt.active {{ r:5.5; stroke:#fff; stroke-width:1.6; }}
  polyline.series.hidden {{ display:none; }}
  circle.pt.hidden {{ display:none; }}
  rect.hit {{ cursor:crosshair; }}
  #tip {{ position:absolute; z-index:5; pointer-events:none; display:none;
         background:rgba(18,18,24,.97); border:1px solid #3f3f4d; border-radius:8px;
         padding:9px 11px; font-size:12px; line-height:1.45; min-width:200px;
         box-shadow:0 10px 26px rgba(0,0,0,.55); transform:translate(-50%,-112%); }}
  #tip.pinned {{ border-color:#7a7a8f; box-shadow:0 0 0 1px #7a7a8f, 0 10px 26px rgba(0,0,0,.55); }}
  #tip .tname {{ font-weight:600; margin-bottom:6px; }}
  #tip .srow {{ display:flex; justify-content:space-between; gap:14px; }}
  #tip .srow b {{ font-variant-numeric:tabular-nums; }}
  #tip .dot {{ width:8px; height:8px; border-radius:50%; display:inline-block;
               margin-right:6px; }}
  #tip .prods {{ color:var(--dim); margin-top:6px; max-width:260px; }}
  #tip .delta {{ margin-top:5px; color:var(--dim); }}
  .cols {{ display:flex; gap:20px; align-items:flex-start; flex-wrap:wrap; }}
  .col {{ flex:1 1 480px; min-width:420px; }}
  h2 {{ font-size:16px; margin:6px 0; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; }}
  th,td {{ border-bottom:1px solid var(--line); padding:4px 6px; text-align:left;
           vertical-align:top; }}
  th {{ color:var(--dim); position:sticky; top:0; background:var(--bg); }}
  td.n {{ color:var(--dim); text-align:right; width:34px; }}
  td.num {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
  td.prod {{ color:var(--dim); font-size:11px; }}
  tbody tr {{ cursor:pointer; }}
  tbody tr:hover {{ background:#20202a; }}
  tbody tr.active {{ background:#2a2333; }}
</style>
</head>
<body>
<h1>randputF — difficulté comparée</h1>
<p class="sub">Coût en ressources brutes cumulé, tech par tech (la chaîne de la
fusée ferme chaque profil). Survole une tech pour le détail, clique pour épingler.</p>
<div class="totals">
  <div class="tot">vanilla<br><b style="color:{vanilla_color}">{vanilla_total}</b></div>
  <div class="tot">seed (mod)<br><b style="color:{mod_color}">{mod_total}</b></div>
  <div class="tot">rapport mod/vanilla<br><b>×{ratio:.2f}</b></div>
</div>
<div class="legend">
  <span data-series="v"><i style="background:{vanilla_color}"></i>{vanilla_label}</span>
  <span data-series="m"><i style="background:{mod_color}"></i>{mod_label}</span>
</div>
<div class="chart" id="chartwrap">
  {svg}
  <div id="tip"></div>
</div>
<div class="cols">{tables}</div>
<script>
const DATA = {data_json};
(function () {{
  const svg = document.getElementById('diffsvg');
  const wrap = document.getElementById('chartwrap');
  const tip = document.getElementById('tip');
  if (!svg || !DATA.points) return;
  const guide = document.getElementById('guide');
  const hits = Array.from(svg.querySelectorAll('.hit'));
  const pts = Array.from(svg.querySelectorAll('circle.pt'));
  const rows = Array.from(document.querySelectorAll('tr.trow'));
  const nf = (v) => Math.round(v).toLocaleString('fr-FR');
  const cols = DATA.colors;
  const labels = DATA.labels;
  let pinned = null;
  let lastRec = null;
  let hidden = {{v:false, m:false}};

  function place(rec) {{
    const r = svg.getBoundingClientRect();
    const w = wrap.getBoundingClientRect();
    const k = r.width / DATA.svw;
    const px = (r.left - w.left) + rec.x * k;
    const py = r.top - w.top + 30;
    tip.style.left = px + 'px';
    tip.style.top = py + 'px';
  }}

  function render(rec) {{
    lastRec = rec;
    const v = hidden.v ? null : rec.v;
    const m = hidden.m ? null : rec.m;
    let h = '';
    const name = (m && m.name) || (v && v.name) || '';
    h += '<div class="tname">#' + (rec.i + 1) + ' — ' + escapeHtml(name) + '</div>';
    for (const [key, d] of [['v', v], ['m', m]]) {{
      if (!d) continue;
      h += '<div class="srow"><span><span class="dot" style="background:' +
           cols[key] + '"></span>' + escapeHtml(labels[key]) + '</span></div>';
      h += '<div class="srow"><span>coût</span><b>' + nf(d.raw) + '</b></div>';
      h += '<div class="srow"><span>cumul</span><b>' + nf(d.cum) + '</b></div>';
      if (d.products && d.products.length)
        h += '<div class="srow prod">' + escapeHtml(d.products.join(', ')) + '</div>';
    }}
    if (v && m && !hidden.v && !hidden.m)
      h += '<div class="srow" style="margin-top:4px;border-top:1px solid #33333d;' +
           'padding-top:4px"><span>écart</span><b>' +
           (m.cum - v.cum >= 0 ? '+' : '') + nf(m.cum - v.cum) + '</b></div>';
    tip.innerHTML = h;
    tip.style.display = 'block';
    guide.style.display = 'block';
    guide.setAttribute('x1', rec.x);
    guide.setAttribute('x2', rec.x);
    pts.forEach((p) => p.classList.toggle('active', +p.dataset.i === rec.i));
    rows.forEach((r) => r.classList.toggle('active', +r.dataset.i === rec.i));
  }}

  function clearVisual() {{
    pts.forEach((p) => p.classList.remove('active'));
    rows.forEach((r) => r.classList.remove('active'));
    tip.style.display = 'none';
    guide.style.display = 'none';
  }}

  function show(rec, pin) {{
    pinned = pin ? rec.i : null;
    tip.classList.toggle('pinned', !!pin);
    render(rec);
    place(rec);
  }}

  function hide() {{ if (pinned === null) clearVisual(); }}

  hits.forEach((hit) => {{
    hit.addEventListener('mouseenter', () => {{
      if (pinned !== null) return;
      render(DATA.points[+hit.dataset.i]);
    }});
    hit.addEventListener('mousemove', () => {{
      if (pinned !== null) return;
      place(DATA.points[+hit.dataset.i]);
    }});
    hit.addEventListener('mouseleave', hide);
    hit.addEventListener('click', (e) => {{
      e.stopPropagation();
      const i = +hit.dataset.i;
      if (pinned === i) {{ pinned = null; clearVisual(); }}
      else show(DATA.points[i], true);
    }});
  }});

  svg.addEventListener('mouseleave', hide);
  wrap.addEventListener('click', () => {{ pinned = null; tip.classList.remove('pinned'); clearVisual(); }});

  rows.forEach((row) => {{
    row.addEventListener('click', (e) => {{
      e.stopPropagation();
      show(DATA.points[+row.dataset.i], true);
      wrap.scrollIntoView({{behavior:'smooth', block:'start'}});
    }});
  }});

  document.querySelectorAll('.legend span').forEach((el) => {{
    el.addEventListener('click', (e) => {{
      e.stopPropagation();
      const s = el.dataset.series;
      hidden[s] = !hidden[s];
      el.classList.toggle('off', hidden[s]);
      svg.querySelectorAll('.series.' + s).forEach((n) => n.classList.toggle('hidden', hidden[s]));
      svg.querySelectorAll('circle.pt.' + s).forEach((n) => n.classList.toggle('hidden', hidden[s]));
      if (pinned !== null) render(DATA.points[pinned]);
      else if (lastRec && tip.style.display === 'block') render(lastRec);
    }});
  }});

  function escapeHtml(s) {{
    return String(s).replace(/[&<>"']/g, (c) => (
      {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
  }}
}}());
</script>
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

    svg, data_json = _chart_svg(
        vanilla_series, mod_series, vanilla_label, mod_label,
        _VANILLA_COLOR, _MOD_COLOR,
    )
    doc = _TEMPLATE.format(
        vanilla_color=_VANILLA_COLOR,
        mod_color=_MOD_COLOR,
        vanilla_total=html.escape(_fmt(vanilla_total)),
        mod_total=html.escape(_fmt(mod_total)),
        ratio=ratio,
        vanilla_label=html.escape(vanilla_label),
        mod_label=html.escape(mod_label),
        svg=svg,
        data_json=data_json,
        tables=_table(vanilla_series, vanilla_label, _VANILLA_COLOR, "v")
        + _table(mod_series, mod_label, _MOD_COLOR, "m"),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path
