"""Point d'entrée CLI : parse les arguments et orchestre les neuf commandes via
service et exporters ; les erreurs attendues deviennent des codes de sortie.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from tool.audit.difficulty import compute_difficulty, summarize_difficulty
from tool.audit.tags import audit_building_tags, audit_item_tags, summarize_tags
from tool.common.db import VanillaDB
from tool.common.version import MOD_NAME_VERSIONED
from tool.common.witness import witness_md5
from tool.exporters.complexity_graph import write_complexity_html
from tool.exporters.difficulty_graph import (
    vanilla_seed_from_dump,
    write_difficulty_graph_html,
)
from tool.exporters.dump_html import write_dump_html
from tool.exporters.mod_seed import build_vanilla_seed
from tool.exporters.report import write_full_report
from tool.exporters.seed_graph import write_seed_graph_html
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import rocket_chain_from_dump, summarize_db
from tool.service import (
    DUMP_PATH_DEFAULT,
    MOD_DIR,
    OUTPUT_DIR,
    REPORT_DIR,
    DumpInvalidError,
    DumpMissingError,
    SeedUnplayableError,
    build_mod,
    current_seed,
    generate_with_retry,
)
from tool.service import build_mod as _build_mod
from tool.service import install_mod as _install_mod
from tool.service import load_config as _load_config
from tool.service import load_db as _load_db_raising
from tool.tester import Progress, run_dump_test


def _load_db(demo: bool, dump_path: Path) -> VanillaDB:
    """Charge la base vanilla demandée par la CLI.

    `demo` sélectionne la base synthétique, sinon `dump_path` désigne le JSON de l'exporter. Retourne la `VanillaDB` chargée ; en cas de dump absent ou invalide, imprime le message du service et termine le processus avec le code 1 (aucune exception ne remonte).
    """
    try:
        return _load_db_raising(demo, dump_path)
    except DumpMissingError as err:
        print(err)
        sys.exit(1)
    except DumpInvalidError as err:
        print(f"[DUMP INVALIDE] {err}")
        sys.exit(1)


def _save_dump(dump_path: Path, dump: dict) -> None:
    """Réécrit le dump avec son cache de simulation, sans le corrompre en cas d'erreur."""
    temporary = dump_path.with_name(dump_path.name + ".tmp")
    temporary.write_text(
        json.dumps(dump, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(dump_path)


def cmd_parse(args: argparse.Namespace) -> None:
    """Charge la base vanilla puis imprime son résumé.

    `args` est le namespace argparse de `randputf parse` (`demo`, `dump`). Écrit le résumé de `summarize_db` sur stdout et retourne `None`.
    """
    db = _load_db(args.demo, Path(args.dump))
    print(summarize_db(db))


def cmd_audit(args: argparse.Namespace) -> None:
    """Audite les tags des bâtiments et des items puis imprime le bilan.

    `args` porte `demo`/`dump`. Fusionne les deux rapports, écrit le résumé sur stdout et termine avec le code 0 si aucun invariant n'est violé, 1 sinon.
    """
    db = _load_db(args.demo, Path(args.dump))
    report = audit_building_tags(db)
    item_report = audit_item_tags(db)
    report.violations += item_report.item_violations
    report.item_violations = item_report.item_violations
    report.item_tag_counts = item_report.item_tag_counts
    report.uncraftable_violations = item_report.uncraftable_violations
    report.items_checked = item_report.items_checked
    print(summarize_tags(db, report))
    sys.exit(0 if report.ok else 1)


def _canonical_name(label: str) -> str:
    """Uniformise `randputF-<version>` en `randputF_<version>`."""
    if label.startswith("randputF-"):
        return f"randputF_{label[len('randputF-'):]}"
    return label


def _source_label(dump_path: str, dump: dict) -> str:
    """Retourne le préfixe canonique de la source pour les HTML (et le dossier sans --mod-dir)."""
    meta = (dump.get("meta") or {})
    label = meta.get("mod_label") or meta.get("dump_label")
    if isinstance(label, str) and label:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-")
        if cleaned:
            return _canonical_name(cleaned)
    stem = Path(dump_path).stem
    if stem.endswith("_dump"):
        stem = stem[:-5]
    return _canonical_name(stem or "dump")


def _vanilla_seed_from_path(dump_path: str) -> dict | None:
    """Dérive une « seed » vanilla depuis un dump sur disque.

    `dump_path` est le chemin du JSON ; retourne le dict seed produit par `vanilla_seed_from_dump`, ou `None` si le fichier est absent/illisible ou ne contient pas les technologies.
    """
    try:
        dump = json.loads(Path(dump_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return vanilla_seed_from_dump(dump)


def _report_retry(attempt: int, seed_value: int, issues: list[str]) -> None:
    """Trace une tentative de génération avec une graine dérivée.

    `attempt` est le numéro de tentative, `seed_value` la graine essayée et `issues` les problèmes du validateur. Écrit une ligne `[RETRY …]` sur stdout et retourne `None`.
    """
    first = issues[0] if issues else "raison inconnue"
    print(f"[RETRY {attempt}] seed {seed_value} non jouable ({first}), dérive...")


def cmd_generate(args: argparse.Namespace) -> None:
    """Génère une seed, assemble le mod dans `<root>/mods/<mod>/` et, sauf
    `--no-html`, écrit les rapports dans `<root>/reports/<mod>/` (`<root>` =
    `--out` ou `output/`).

    `args` porte `demo`, `dump`, `seed`, `out`, `install` et `no_html`. `--install`
    copie le mod dans Factorio et l'active dans `mod-list.json`, sans toucher aux
    rapports. Retourne `None` et termine avec le code 2 après 10 échecs.
    """
    db = _load_db(args.demo, Path(args.dump))
    cfg = _load_config()

    # Seed tirée de l'horloge (ms) : partie unique à chaque génération. Avec
    # ``--seed N`` la dérivation reste déterministe (N+1, N+2…) pour ne jamais
    # remplacer silencieusement la valeur demandée par l'horloge.
    base = args.seed if args.seed is not None else current_seed()

    try:
        seed, db = generate_with_retry(
            db, cfg, base, on_attempt=_report_retry
        )
    except SeedUnplayableError as err:
        for issue in err.issues[:10]:
            print(f"[INVALIDE] {issue}")
        sys.exit(2)

    root = Path(args.out) if args.out else OUTPUT_DIR
    mod_path = _build_mod(seed, root / "mods")
    report_dir = root / "reports" / MOD_NAME_VERSIONED
    report_dir.mkdir(parents=True, exist_ok=True)
    print(f"Seed {db.seed_value} valide, mod assemblé dans {mod_path}")

    if args.no_html:
        print("Rapports HTML ignorés (--no-html).")
    else:
        html_path = report_dir / "seed.graph.html"
        write_seed_graph_html(seed, html_path)
        if html_path.exists():
            print(f"Graphe interactif (cliquable) exporté dans {html_path}")
        else:
            print("Graphe interactif ignoré : Graphviz (dot) n'est pas installé.")
        cx_path = report_dir / "seed.complexity.html"
        write_complexity_html(seed, cx_path, db)
        print(f"Rapport de complexité exporté dans {cx_path}")

        vanilla_seed = None if args.demo else _vanilla_seed_from_path(args.dump)
        if vanilla_seed is not None:
            diff_path = report_dir / "seed.difficulty.html"
            write_difficulty_graph_html(
                seed,
                vanilla_seed,
                diff_path,
                context=f"Graine {db.seed_value} — dump vanilla {Path(args.dump).name}",
            )
            print(f"Comparaison de difficulté vanilla vs mod exportée dans {diff_path}")
        else:
            print("Comparaison vanilla ignorée : dump sans technologies (relancer l'exporter).")

    if args.install:
        paths = cfg.get("paths", {})
        raw_path = (paths.get("factorio_mods") or "").strip()
        mods_dir = Path(raw_path).expanduser() if raw_path else None
        if mods_dir is not None and mods_dir.is_dir():
            _install_mod(seed, mods_dir)
            print(f"Mod installé dans {mods_dir}/")
        elif not raw_path:
            print("Aucun dossier mods configuré (paths.factorio_mods vide dans config/user.yaml).")
        else:
            print(f"Dossier Factorio mods introuvable ({raw_path})")


def cmd_compare(args: argparse.Namespace) -> None:
    """Génère une seed et écrit la comparaison de difficulté avec le vanilla.

    `args` fournit `dump`, `seed` et `out` (`demo` est refusé) ; le HTML comparatif
    va dans `<out>/reports/compare/` (défaut `output/`). Retourne `None`.
    """
    if args.demo:
        sys.exit("La comparaison nécessite le dump vanilla (pas --demo).")
    db = _load_db(False, Path(args.dump))
    cfg = _load_config()
    db.seed_value = args.seed if args.seed is not None else int(time.time() * 1000)
    seed = generate_seed(db, config=cfg)

    vanilla_seed = _vanilla_seed_from_path(args.dump)
    if vanilla_seed is None:
        sys.exit(
            "Dump sans technologies : relance l'exporter dans Factorio puis "
            "remplace data/vanilla_dump.json (voir README, système de dev)."
        )

    out_dir = (Path(args.out) if args.out else OUTPUT_DIR) / "reports" / "compare"
    path = out_dir / f"seed.difficulty.{db.seed_value}.html"
    write_difficulty_graph_html(
        seed,
        vanilla_seed,
        path,
        context=f"Seed {db.seed_value} — dump vanilla {Path(args.dump).name}",
    )

    vanilla_total = compute_difficulty(vanilla_seed).total
    mod_total = compute_difficulty(seed).total
    ratio = (mod_total / vanilla_total) if vanilla_total else 0.0
    print(f"Seed {db.seed_value} — difficulté comparée (ressources brutes) :")
    print(f"  vanilla : {vanilla_total:12.0f}")
    print(f"  mod     : {mod_total:12.0f}   (×{ratio:.2f} vs vanilla)")
    print(f"HTML : {path}")


def cmd_report(args: argparse.Namespace) -> None:
    """Génère le rapport complet du dump vanilla et contrôle les données lues.

    `args` porte `dump`, `out`, `playthrough` et `no_cache`. Le HTML par défaut va dans `output/reports/vanilla/` ; produit complexité, difficulté et, sur option, la partie simulée. Retourne `None`.
    """
    dump_path = Path(args.dump)
    try:
        dump = json.loads(dump_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        sys.exit(f"Dump illisible ({dump_path}) : {err}")

    seed = build_vanilla_seed(dump)
    if not seed.get("technologies"):
        sys.exit(
            "Dump sans technologies : relance l'exporter dans Factorio puis "
            "remplace le dump (voir README, système de dev)."
        )

    game_version = (dump.get("meta") or {}).get("game_version", "inconnue")
    out = Path(args.out) if args.out else REPORT_DIR / "vanilla" / "vanilla.report.html"
    skip = {"playthrough"} if not getattr(args, "playthrough", False) else set()
    if getattr(args, "no_cache", False):
        skip.add("cache")
    skip = frozenset(skip)
    result = write_full_report(
        seed,
        out,
        None,
        vanilla_seed=seed,
        dump=dump,
        title=f"Factorio vanilla {game_version} — rapport complet",
        playthrough_title=f"Factorio vanilla {game_version} — partie simulée",
        skip=skip,
    )
    if result.get("cache_written"):
        _save_dump(dump_path, dump)

    analysis = result["analysis"]
    stats = analysis.get("item_stats") or {}
    print(f"Dump    : {dump_path} (Factorio {game_version})")
    if "playthrough" in skip:
        print("Simulation : ignorée (--playthrough pour l’activer)")
        print("Complexité : graphe mémoïsé du dump")
    else:
        print(f"Entrées : {len(stats)} items/fluides simulés")
        if result.get("cache_hit"):
            print("Cache   : simulation reprise du dump")
        elif result.get("cache_written"):
            print("Cache   : simulation enregistrée dans le dump")
        print(f"Crafts  : {analysis.get('total_crafts', 0)}")
        print(f"Minage  : {analysis.get('mining_seconds', 0)} s")
        buildings = analysis.get("buildings") or []
        print(f"Bâtiments : {', '.join(buildings) or '—'}")

        external = analysis.get("external_items") or []
        if external:
            print(f"[ATTENTION] fournis en externe : {', '.join(external)}")
        else:
            print("[OK] aucun item fourni en externe")

        mined = [name for name, stat in stats.items() if stat.get("mined", 0) > 0]
        if mined and not analysis.get("mining_seconds"):
            print("[ATTENTION] temps de minage absent du dump (mineable_properties) : relance l'exporter")

        entities = dump.get("entities") or {}
        pumps = [
            name
            for name, entity in entities.items()
            if isinstance(entity, dict)
            and entity.get("pumping_speed") is not None
            and not entity.get("pumped_fluid")
            and not entity.get("pumped_fluids")
        ]
        if pumps:
            print(
                f"[ATTENTION] pumped_fluid absent ({', '.join(pumps[:5])}) : "
                "relance l'exporter récent"
            )
        # Produits de lancement : source de vérité = ``rocket_launch_products``
        # déclaré par les items ou les entités du dump, sans nom supposé.
        launch_products_sources = [
            entry.get("rocket_launch_products")
            for section in ((dump.get("items") or {}), entities)
            for entry in section.values()
            if isinstance(entry, dict) and entry.get("rocket_launch_products")
        ]
        if not launch_products_sources:
            print("[ATTENTION] produits de lancement absents : relance l'exporter récent")

        untagged = [row["name"] for row in result["rows"] if row["tags"] == "—"]
        if untagged:
            print(f"[ATTENTION] sans tag : {', '.join(untagged[:10])}")
        else:
            print("[OK] tous les items/fluides ont un tag")

        prog = result.get("progression") or {}
        print(
            f"[OK] chaîne de progression : {prog.get('count', 0)} items/fluides "
            f"({prog.get('packs', 0)} packs de science)"
        )

        for product in rocket_chain_from_dump(dump).get("launch_products") or ():
            row = stats.get(product)
            if row is None:
                continue
            print(
                f"[OK] lancement ({product}) : {row.get('crafts', 0)} lancement(s), "
                f"{row.get('produced', 0)} produits"
            )
    print(f"Rapport : {out}")


def cmd_test(args: argparse.Namespace) -> None:
    """Teste un dump ou un mod existant et écrit les vues HTML non désactivées.

    `args` porte `dump`, `mod_dir`, `out`, `--playthrough` et les options
    `--no-...`. Sans `mod_dir`, l'état testé vient directement du dump. Avec
    `mod_dir`, l'état déjà assemblé du mod est lu depuis `seed/seed.json`. Les
    vues vont dans `<root>/reports/<source ou nom du mod>/` (défaut
    `output/reports/`). Le graphe dépend de Graphviz. Aucune graine n'est tirée
    et aucun mod n'est généré.
    """
    skip = {"playthrough"}
    flags = (
        ("no_checks", "checks"),
        ("no_complexity", "complexity"),
        ("no_difficulty", "difficulty"),
        ("no_playthrough", "playthrough"),
        ("no_cache", "cache"),
        ("no_report_html", "report-html"),
        ("no_dump_html", "dump-html"),
        ("no_graph_html", "graph-html"),
    )
    for attribute, name in flags:
        if getattr(args, attribute, False):
            skip.add(name)
    if getattr(args, "playthrough", False):
        skip.discard("playthrough")
    if getattr(args, "no_html", False):
        skip.update(("report-html", "dump-html", "graph-html"))

    progress = Progress()
    progress.start()
    try:
        dump_path = Path(args.dump)
        progress.enter("acquisition", f"lecture de {dump_path.name}")
        try:
            dump = json.loads(dump_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            sys.exit(f"Dump illisible ({dump_path}) : {err}")
        progress.update(30, "dump lu")

        state = None
        if args.mod_dir:
            state_path = Path(args.mod_dir) / "seed" / "seed.json"
            progress.update(60, "lecture de l'état du mod")
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as err:
                sys.exit(f"État du mod illisible ({state_path}) : {err}")
            progress.update(70, "état du mod lu")

        progress.update(80, "chargement de la base vanilla")
        db = _load_db(False, dump_path)
        if Path(args.dump).resolve() == DUMP_PATH_DEFAULT.resolve():
            baseline_seed = build_vanilla_seed(dump)
        else:
            try:
                baseline_seed = build_vanilla_seed(
                    json.loads(DUMP_PATH_DEFAULT.read_text(encoding="utf-8"))
                )
            except (OSError, ValueError) as err:
                sys.exit(f"Baseline vanilla illisible ({DUMP_PATH_DEFAULT}) : {err}")
        progress.update(90, "base vanilla chargée")
        source = _source_label(str(dump_path), dump)
        out_name = _canonical_name(Path(args.mod_dir).name) if args.mod_dir else None
        out_dir = Path(args.out) if args.out else REPORT_DIR
        result = run_dump_test(
            db,
            dump,
            out_dir,
            source=source,
            state=state,
            baseline_seed=baseline_seed,
            out_name=out_name,
            progress=progress,
            skip=frozenset(skip),
        )
        if result.cache_written:
            _save_dump(dump_path, dump)
    finally:
        progress.finish("arrêt du testeur")

    check = result.check
    skipped = result.skipped
    print(f"Source : {dump_path} → {source}")
    if result.cache_hit:
        print("Cache   : simulation reprise du dump")
    elif result.cache_written:
        print("Cache   : simulation enregistrée dans le dump")
    if check.skipped:
        print("Contrôle : ignoré (--no-checks)")
    else:
        print(f"Contrôle : {'OK' if not check.issues else f'{len(check.issues)} problème(s)'}")
    counts = result.coverage.get("counts") or {}
    print(
        "Couverture : "
        + " · ".join(
            f"{label} {counts.get(label, 0)}"
            for label in ("Consommé", "Partiel", "À consommer", "Cosmétique")
        )
    )
    for issue in check.issues[:10]:
        print(f"[INVALIDE] {issue}")
    if check.skipped:
        print("Rejeu : ignoré (--no-checks)")
    else:
        print(
            f"Rejeu : {check.researched}/{check.total_techs} techs, "
            f"{'victoire' if check.victory else 'défaite'}"
        )
    if check.blocker:
        print("[BLOQUÉ]")
        for line in str(check.blocker).splitlines():
            print(f"  {line}")
    if "difficulty" in skipped:
        print("Difficulté : ignorée (--no-difficulty)")
    elif result.difficulty_total is None:
        print("Difficulté : non calculable sur ce dump")
    else:
        print(f"Difficulté : {result.difficulty_total:,.0f} ressources brutes")
    if "dump-html" in skipped:
        print("Dump    : ignoré (--no-dump-html)")
    else:
        print(f"Dump    : {result.dump_html}")
    if "graph-html" in skipped:
        print("Graphe  : ignoré (--no-graph-html)")
    else:
        print(f"Graphe  : {result.graph_html or 'ignoré (Graphviz absent)'}")
    if "report-html" in skipped:
        print("Rapport : ignoré (--no-report-html)")
    else:
        print(f"Rapport : {result.report_html}")
    if not check.ok and "checks" not in skipped:
        sys.exit(2)


def cmd_dump(args: argparse.Namespace) -> None:
    """Écrit le navigateur HTML du dump.

    `args` porte `dump` et `out`. La page autonome contient l'inventaire et les sections détaillées ; retourne `None`.
    """
    dump_path = Path(args.dump)
    try:
        dump = json.loads(dump_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        sys.exit(f"Dump illisible ({dump_path}) : {err}")
    out = Path(args.out) if args.out else REPORT_DIR / "vanilla" / "vanilla.dump.html"
    path = write_dump_html(dump, out)
    print(f"Navigateur du dump : {path}")


def cmd_difficulty(args: argparse.Namespace) -> None:
    """Génère une seed et imprime son ardoise de difficulté.

    `args` porte `demo`, `dump` et `seed`. Affiche les coûts bruts par ressource et la chaîne de progression ; retourne `None`.
    """
    db = _load_db(args.demo, Path(args.dump))
    cfg = _load_config()
    db.seed_value = args.seed if args.seed is not None else int(time.time() * 1000)
    seed = generate_seed(db, config=cfg)
    report = compute_difficulty(seed)
    print(f"Ardoise de la seed {db.seed_value} (recettes primaires, DAG)")
    print(summarize_difficulty(report))


def cmd_witness(args: argparse.Namespace) -> None:
    """Assemble le mod d'une seed et calcule son md5 canonique ; avec `--expect`,
    vérifie la concordance (sortie 1 si divergence).

    `args` porte `demo`, `dump`, `seed` (défaut 5), `out` et `expect`. Retourne
    `None`.
    """
    db = _load_db(args.demo, Path(args.dump))
    db.seed_value = args.seed
    cfg = _load_config()
    seed = generate_seed(db, config=cfg)
    out_dir = Path(args.out) if args.out else MOD_DIR
    mod_path = build_mod(seed, out_dir)
    digest = witness_md5(mod_path)
    print(f"seed_value: {db.seed_value}")
    print(f"temoins   : {digest}")
    if args.expect:
        ok = digest == args.expect
        print(f"attendu   : {args.expect} -> {'OK' if ok else 'DIVERGENT'}")
        if not ok:
            sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    """Point d'entrée de la CLI `randputf`.

    `argv` est la liste d'arguments (ou `None` pour `sys.argv`). Parse la
    sous-commande, l'exécute et retourne `None` ; les erreurs attendues deviennent
    des codes de sortie.
    """
    parser = argparse.ArgumentParser(prog="randputf", description="Generateur de seeds randputF")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Charge et resume la base vanilla")
    p_parse.add_argument("--demo", action="store_true", help="Utilise une base synthétique")
    p_parse.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_parse.set_defaults(func=cmd_parse)

    p_audit = sub.add_parser("audit", help="Audite les tags bâtiments et items")
    p_audit.add_argument("--demo", action="store_true", help="Utilise une base synthétique")
    p_audit.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_audit.set_defaults(func=cmd_audit)

    p_diff = sub.add_parser("difficulty", help="Ardoise de la seed : ressources brutes pour finir une run")
    p_diff.add_argument("--demo", action="store_true", help="Utilise une base synthétique")
    p_diff.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_diff.add_argument("--seed", type=int, default=None,
                        help="Seed à imposer (défaut : tirée du temps courant en millisecondes)")
    p_diff.set_defaults(func=cmd_difficulty)

    p_cmp = sub.add_parser("compare", help="Compare la difficulté d'une seed à la baseline vanilla (HTML)")
    p_cmp.add_argument("--demo", action="store_true", help="Utilise une base synthétique (incompatible)")
    p_cmp.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_cmp.add_argument("--seed", type=int, default=None,
                       help="Seed à imposer (défaut : tirée du temps courant en millisecondes)")
    p_cmp.add_argument("--out", default=None, help="Racine de sortie : HTML dans <out>/reports/compare/ (défaut : output/)")
    p_cmp.set_defaults(func=cmd_compare)

    p_report = sub.add_parser(
        "report", help="Genere le rapport complet du dump vanilla (HTML + resume/controles)"
    )
    p_report.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_report.add_argument(
        "--out", default=None,
        help="Chemin du HTML (défaut : output/reports/vanilla/vanilla.report.html)",
    )
    p_report.add_argument(
        "--playthrough", action="store_true",
        help="Activer la simulation complète (désactivée par défaut)",
    )
    p_report.add_argument(
        "--no-cache", action="store_true",
        help="Ignorer la simulation persistée dans le dump",
    )
    p_report.set_defaults(func=cmd_report)

    p_test = sub.add_parser(
        "test", help="Teste un dump ou un mod existant et écrit les vues HTML actives"
    )
    p_test.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_test.add_argument(
        "--mod-dir", default=None,
        help="Mod déjà assemblé : utilise son seed/seed.json sans rien générer",
    )
    p_test.add_argument(
        "--out", default=None,
        help="Racine des rapports HTML (défaut : output/reports/)",
    )
    p_test.add_argument(
        "--no-checks", action="store_true",
        help="Ignorer validation statique et rejeu",
    )
    p_test.add_argument(
        "--no-complexity", action="store_true",
        help="Ignorer le calcul de complexité dans le rapport",
    )
    p_test.add_argument(
        "--no-difficulty", action="store_true",
        help="Ignorer le calcul de difficulté",
    )
    p_test.add_argument(
        "--playthrough", action="store_true",
        help="Activer la simulation complète (désactivée par défaut)",
    )
    p_test.add_argument(
        "--no-playthrough", action="store_true",
        help="Ignorer la partie simulée (défaut ; --playthrough prévaut si fourni)",
    )
    p_test.add_argument(
        "--no-cache", action="store_true",
        help="Ignorer la simulation persistée dans le dump",
    )
    p_test.add_argument(
        "--no-report-html", action="store_true",
        help="Ne pas ecrire le rapport HTML",
    )
    p_test.add_argument(
        "--no-dump-html", action="store_true",
        help="Ne pas ecrire le navigateur du dump",
    )
    p_test.add_argument(
        "--no-graph-html", action="store_true",
        help="Ne pas ecrire le graphe HTML",
    )
    p_test.add_argument(
        "--no-html", action="store_true",
        help="Ne pas écrire les rapports HTML (graphe, complexité, difficulté si disponible)",
    )
    p_test.set_defaults(func=cmd_test)

    p_dump = sub.add_parser(
        "dump", help="Navigateur HTML du dump : inventaire A→Z, tuiles, entités…"
    )
    p_dump.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_dump.add_argument(
        "--out", default=None,
        help="Chemin du HTML (défaut : output/reports/vanilla/vanilla.dump.html)",
    )
    p_dump.set_defaults(func=cmd_dump)

    p_gen = sub.add_parser("generate", help="Génère, valide puis exporte une seed dans le mod")
    p_gen.add_argument("--demo", action="store_true", help="Utilise une base synthétique")
    p_gen.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_gen.add_argument("--out", default=None, help="Racine : mod dans <out>/mods/<mod>/, HTML dans <out>/reports/<mod>/ (défaut : output/)")
    p_gen.add_argument("--seed", type=int, default=None, help="Seed à imposer (défaut : tirée du temps courant en millisecondes)")
    p_gen.add_argument("--install", action="store_true", help="Tente d'installer le mod dans Factorio (paths.factorio_mods)")
    p_gen.add_argument("--no-html", action="store_true", help="Ne pas écrire les rapports HTML (graphe, complexité, difficulté si disponible)")
    p_gen.set_defaults(func=cmd_generate)

    p_witness = sub.add_parser("witness", help="MD5 canonique du mod assemblé (témoin de déterminisme)")
    p_witness.add_argument("--demo", action="store_true", help="Utilise une base synthétique")
    p_witness.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_witness.add_argument("--seed", type=int, default=5, help="Seed à assembler puis hacher (défaut : 5, le témoin)")
    p_witness.add_argument("--out", default=None, help="Dossier des mods (défaut : output/mods/)")
    p_witness.add_argument("--expect", default=None, help="MD5 attendu ; exit 1 si divergence (utile en CI)")
    p_witness.set_defaults(func=cmd_witness)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
