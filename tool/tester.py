"""Testeur de dump randputF : contrôler, rejouer, mesurer et rendre.

Les noms ci-dessous sont stables et servent de référence à la CLI, aux tests
et à la documentation :

- ``acquisition`` : lit le dump fourni par l'exporter ;
- ``controle`` : ``validate_seed`` — cycles, invariants et unicité des
  déblocages ;
- ``rejeu`` : ``play`` — partie simulée depuis les faits du dump ;
- ``mesure`` : complexité, difficulté et partie simulée ;
- ``rapport`` : trois fichiers HTML préfixés par la source.

Aucune graine n'est tirée ici : l'état testé vient du dump, ou d'un mod déjà
assemblé quand la CLI fournit explicitement son état.
"""

from __future__ import annotations

import html as _html
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tool.audit.difficulty import compute_difficulty
from tool.audit.fields import classify_dump_fields
from tool.exporters.dump_html import write_dump_html
from tool.exporters.mod_seed import build_vanilla_seed
from tool.exporters.report import write_full_report
from tool.exporters.seed_graph import write_seed_graph_html
from tool.replay.player import play
from tool.validator.solver import validate_seed

STAGES = ("acquisition", "controle", "rejeu", "mesure", "rapport")
SECTIONS = ("controles", "couverture-dump", "complexite-courbes", "difficulte", "partie-simulee")


@dataclass
class CheckReport:
    """Résultat des étapes ``controle`` et ``rejeu`` du testeur."""

    issues: list[str] = field(default_factory=list)
    victory: bool = False
    blocker: str | None = None
    researched: int = 0
    total_techs: int = 0

    @property
    def ok(self) -> bool:
        """Indique si l'état passe le contrôle et le rejeu."""
        return not self.issues and self.victory

    def as_dict(self) -> dict[str, Any]:
        """Retourne le résultat sous forme de dict pour le rapport HTML."""
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "victory": self.victory,
            "blocker": self.blocker,
            "researched": self.researched,
            "total_techs": self.total_techs,
        }


@dataclass
class TesterReport:
    """Résultat complet d'un passage du testeur."""

    check: CheckReport
    dump_html: Path
    graph_html: Path | None
    report_html: Path
    difficulty_total: float | None
    coverage: dict


def check_state(db: Any, state: dict) -> CheckReport:
    """Exécute le contrôle statique puis le rejeu sur un état issu du dump."""
    issues = validate_seed(state)
    replay = play(db, state)
    return CheckReport(
        issues=list(issues),
        victory=bool(replay.victory),
        blocker=str(replay.blocker) if replay.blocker else None,
        researched=int(replay.researched),
        total_techs=int(replay.total_techs),
    )


def _write_graph_fallback(state: dict, path: Path, source: str) -> None:
    """Écrit une vue graphe textuelle quand Graphviz ne peut pas rendre le SVG."""
    techs = sorted(tech.get("id", "") for tech in state.get("technologies") or [])
    recipes = sorted(recipe.get("name", "") for recipe in state.get("recipes") or [])
    tech_html = "".join(f"<li>{_html.escape(name)}</li>" for name in techs[:1000])
    recipe_html = "".join(f"<li>{_html.escape(name)}</li>" for name in recipes[:1000])
    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>{_html.escape(source)} — graphe</title>"
        "<style>body{font:14px system-ui,sans-serif;background:#16161d;color:#ddd;margin:24px}"
        "h1{font-size:20px}ul{columns:3;line-height:1.5}li{overflow-wrap:anywhere}</style></head><body>"
        f"<h1>{_html.escape(source)} — graphe (vue textuelle)</h1>"
        f"<p>Rendu SVG indisponible : {len(techs)} technologies, {len(recipes)} recettes.</p>"
        f"<h2>Technologies</h2><ul>{tech_html}</ul>"
        f"<h2>Recettes</h2><ul>{recipe_html}</ul></body></html>"
    )
    path.write_text(document, encoding="utf-8")


def run_dump_test(
    db: Any,
    dump: dict,
    out_dir: Path,
    *,
    source: str = "dump",
    state: dict | None = None,
    title: str | None = None,
) -> TesterReport:
    """Teste un état déterministe et écrit les trois vues HTML préfixées."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage = classify_dump_fields(dump)
    tested = state if state is not None else build_vanilla_seed(dump)
    check = check_state(db, tested)

    dump_html = write_dump_html(dump, out_dir / f"{source}.dump.html")
    graph_html = out_dir / f"{source}.graph.html"
    try:
        write_seed_graph_html(tested, graph_html)
    except (OSError, subprocess.CalledProcessError):
        _write_graph_fallback(tested, graph_html, source)
        graph_path = graph_html
    else:
        graph_path = graph_html if graph_html.exists() else None

    game_version = (dump.get("meta") or {}).get("game_version", "inconnue")
    if title is None:
        title = f"randputF — test de {source} (Factorio {game_version})"
    result = write_full_report(
        tested,
        out_dir / f"{source}.report.html",
        db,
        vanilla_seed=tested,
        dump=dump,
        title=title,
        playthrough_title=f"Partie simulée — {source}",
        mod_label="état testé",
        vanilla_label="dump",
        checks=check.as_dict(),
        dump_coverage=coverage,
    )

    try:
        difficulty_total = float(compute_difficulty(tested).total)
    except (ArithmeticError, KeyError, TypeError, ValueError):
        difficulty_total = None

    return TesterReport(
        check=check,
        dump_html=dump_html,
        graph_html=graph_path,
        report_html=Path(result["path"]),
        difficulty_total=difficulty_total,
        coverage=coverage,
    )


__all__ = [
    "STAGES",
    "SECTIONS",
    "CheckReport",
    "TesterReport",
    "check_state",
    "run_dump_test",
]
