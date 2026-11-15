"""Point d'entrée CLI de randputF (``python -m tool``).

Expose les commandes ``parse``, ``audit``, ``difficulty``, ``compare``,
``generate`` et ``witness``. Chaque commande valide ses arguments via
``argparse`` puis délègue à ``tool.service`` (chargement de la base, config,
génération, assemblage) ; ce module ne fait que traduire les exceptions du
service en codes de sortie et formater la sortie console.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from tool.audit.difficulty import compute_difficulty, summarize_difficulty
from tool.audit.tags import audit_building_tags, audit_item_tags, summarize_tags
from tool.common.db import VanillaDB
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
from tool.parsers.vanilla import summarize_db
from tool.service import (
    DUMP_PATH_DEFAULT,
    OUTPUT_DIR,
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
    print(f"[RETRY {attempt}] seed {seed_value} non jouable ({first}), derive...")


def cmd_generate(args: argparse.Namespace) -> None:
    """Génère une seed puis l'assemble en mod et écrit ses rapports.

    `args` porte les options CLI (`demo`, `dump`, `seed`, `out`, `install`). La fonction charge la base et la config, génère avec reprise sur graine dérivée, écrit `seed.json`/`seed.lua` et le graphe HTML, puis installe le mod si demandé. Retourne `None` et termine avec le code 2 après 10 échecs.
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

    if args.install:
        paths = cfg.get("paths", {})
        raw_path = (paths.get("factorio_mods") or "").strip()
        mods_dir = Path(raw_path).expanduser() if raw_path else None
        if mods_dir is not None and mods_dir.is_dir():
            _install_mod(seed, mods_dir)
            print(f"Seed {db.seed_value} valide, mod installe dans {mods_dir}/")
        else:
            mod_path = _build_mod(seed, OUTPUT_DIR)
            if not raw_path:
                print("Aucun dossier mods configure (paths.factorio_mods vide dans config/user.yaml).")
            else:
                print(f"Dossier Factorio mods introuvable ({raw_path})")
            print(f"Seed {db.seed_value} valide, mod assemble dans {mod_path}")
            print("Copie-le manuellement dans ton dossier mods Factorio.")
    else:
        out_dir = Path(args.out) if args.out else OUTPUT_DIR
        mod_path = _build_mod(seed, out_dir)
        html_path = mod_path / "seed.graph.html"
        write_seed_graph_html(seed, html_path)
        print(f"Seed {db.seed_value} valide, mod assemblé dans {mod_path}")
        if html_path.exists():
            print(f"Graphe interactif (cliquable) exporté dans {html_path}")
        else:
            print("Graphe interactif ignoré : Graphviz (dot) n'est pas installé.")
        cx_path = mod_path / "seed.complexity.html"
        write_complexity_html(seed, cx_path, db)
        print(f"Rapport de complexité exporté dans {cx_path}")

        vanilla_seed = None if args.demo else _vanilla_seed_from_path(args.dump)
        if vanilla_seed is not None:
            diff_path = mod_path / "seed.difficulty.html"
            write_difficulty_graph_html(seed, vanilla_seed, diff_path)
            print(f"Comparaison de difficulté vanilla vs mod exportée dans {diff_path}")
        else:
            print("Comparaison vanilla ignorée : dump sans technologies (relancer l'exporter).")


def cmd_compare(args: argparse.Namespace) -> None:
    """Génère une seed et écrit la comparaison de difficulté avec le vanilla.

    `args` fournit `demo`, `dump`, `seed` et `out`. La baseline vanilla est dérivée du dump ; le HTML comparatif est écrit dans `out`. Retourne `None`.
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

    out_dir = Path(args.out) if args.out else OUTPUT_DIR
    path = out_dir / f"seed.difficulty.{db.seed_value}.html"
    write_difficulty_graph_html(seed, vanilla_seed, path)

    vanilla_total = compute_difficulty(vanilla_seed).total
    mod_total = compute_difficulty(seed).total
    ratio = (mod_total / vanilla_total) if vanilla_total else 0.0
    print(f"Seed {db.seed_value} — difficulté comparée (ressources brutes) :")
    print(f"  vanilla : {vanilla_total:12.0f}")
    print(f"  mod     : {mod_total:12.0f}   (×{ratio:.2f} vs vanilla)")
    print(f"HTML : {path}")


def cmd_report(args: argparse.Namespace) -> None:
    """Génère le rapport complet du dump vanilla et contrôle les données lues.

    `args` porte `demo`, `dump`, `seed` et `out`. Produit complexité, difficulté et partie simulée, imprime un résumé et des avertissements sur les données manquantes. Retourne `None`.
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
    out = Path(args.out) if args.out else OUTPUT_DIR / "vanilla.report.html"
    result = write_full_report(
        seed,
        out,
        None,
        vanilla_seed=seed,
        dump=dump,
        title=f"Factorio vanilla {game_version} — rapport complet",
        playthrough_title=f"Factorio vanilla {game_version} — partie simulée",
    )

    analysis = result["analysis"]
    stats = analysis.get("item_stats") or {}
    print(f"Dump    : {dump_path} (Factorio {game_version})")
    print(f"Entrées : {len(stats)} items/fluides simulés")
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
        and (
            entity.get("type") == "offshore-pump"
            or entity.get("pumping_speed") is not None
        )
        and not entity.get("pumped_fluid")
    ]
    if pumps:
        print(
            f"[ATTENTION] pumped_fluid absent ({', '.join(pumps[:5])}) : "
            "relance l'exporter récent"
        )
    # Produits de lancement : source de vérité = l'ITEM lancé (ex. satellite,
    # ItemWithInventoryPrototype::rocket_launch_products) ; repli : le silo.
    launch_products_sources = [
        entry.get("rocket_launch_products")
        for entry in (dump.get("items") or {}).values()
        if isinstance(entry, dict) and entry.get("rocket_launch_products")
    ]
    silo = entities.get("rocket-silo") or {}
    if isinstance(silo, dict) and silo.get("rocket_launch_products"):
        launch_products_sources.append(silo["rocket_launch_products"])
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

    space = stats.get("space-science-pack")
    if space is not None:
        print(
            f"[OK] space science : {space.get('crafts', 0)} lancement(s), "
            f"{space.get('produced', 0)} packs"
        )
    print(f"Rapport : {out}")


def cmd_dump(args: argparse.Namespace) -> None:
    """Écrit le navigateur HTML du dump.

    `args` porte `dump` et `out`. La page autonome contient l'inventaire et les sections détaillées ; retourne `None`.
    """
    dump_path = Path(args.dump)
    try:
        dump = json.loads(dump_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        sys.exit(f"Dump illisible ({dump_path}) : {err}")
    out = Path(args.out) if args.out else OUTPUT_DIR / "vanilla.dump.html"
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
    """Assemble le mod d'une seed et vérifie son témoin canonique.

    `args` porte `seed` (défaut 5) et `expect`. Imprime le md5 canonique ; si `expect` est fourni et diffère, termine avec le code 1. Retourne `None`.
    """
    db = _load_db(args.demo, Path(args.dump))
    db.seed_value = args.seed
    cfg = _load_config()
    seed = generate_seed(db, config=cfg)
    out_dir = Path(args.out) if args.out else OUTPUT_DIR
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

    `argv` est la liste d'arguments (ou `None` pour `sys.argv`). Parse la sous-commande, l'exécute et retourne `None` ; les erreurs sont converties en codes de sortie par les commandes.
    """
    parser = argparse.ArgumentParser(prog="randputf", description="Generateur de seeds randputF")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Charge et resume la base vanilla")
    p_parse.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_parse.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_parse.set_defaults(func=cmd_parse)

    p_audit = sub.add_parser("audit", help="Audite les tags de bâtiments (invariants C8)")
    p_audit.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_audit.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_audit.set_defaults(func=cmd_audit)

    p_diff = sub.add_parser("difficulty", help="Ardoise de la seed : ressources brutes pour finir une run")
    p_diff.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_diff.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_diff.add_argument("--seed", type=int, default=None,
                        help="Seed a imposer (defaut: tiree du temps courant en millisecondes)")
    p_diff.set_defaults(func=cmd_difficulty)

    p_cmp = sub.add_parser("compare", help="Compare la difficulte d'une seed a la baseline vanilla (HTML)")
    p_cmp.add_argument("--demo", action="store_true", help="Utilise une base synthetique (incompatible)")
    p_cmp.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_cmp.add_argument("--seed", type=int, default=None,
                       help="Seed a imposer (defaut: tiree du temps courant en millisecondes)")
    p_cmp.add_argument("--out", default=None, help="Dossier de sortie du HTML (defaut: output/)")
    p_cmp.set_defaults(func=cmd_compare)

    p_report = sub.add_parser(
        "report", help="Genere le rapport complet du dump vanilla (HTML + resume/controles)"
    )
    p_report.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_report.add_argument(
        "--out", default=None,
        help="Chemin du HTML (defaut: output/vanilla.report.html)",
    )
    p_report.set_defaults(func=cmd_report)

    p_dump = sub.add_parser(
        "dump", help="Navigateur HTML du dump : inventaire A→Z, tuiles, entités…"
    )
    p_dump.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_dump.add_argument(
        "--out", default=None,
        help="Chemin du HTML (defaut: output/vanilla.dump.html)",
    )
    p_dump.set_defaults(func=cmd_dump)

    p_gen = sub.add_parser("generate", help="Genere, valide puis exporte une seed dans le mod")
    p_gen.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_gen.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_gen.add_argument("--out", default=None, help="Dossier de sortie (defaut: output/randputF_<version>)")
    p_gen.add_argument("--seed", type=int, default=None, help="Seed a imposer (defaut: tiree du temps courant en millisecondes)")
    p_gen.add_argument("--install", action="store_true", help="Installe le mod directement dans Factorio")
    p_gen.set_defaults(func=cmd_generate)

    p_witness = sub.add_parser("witness", help="Md5 canonique du mod assemble (temoin de determinisme)")
    p_witness.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_witness.add_argument("--dump", default=str(DUMP_PATH_DEFAULT))
    p_witness.add_argument("--seed", type=int, default=5, help="Seed a assembler puis hacher (defaut: 5, le temoin)")
    p_witness.add_argument("--out", default=None, help="Dossier de sortie (defaut: output/)")
    p_witness.add_argument("--expect", default=None, help="Md5 attendu ; exit 1 si divergence (utile en CI)")
    p_witness.set_defaults(func=cmd_witness)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
