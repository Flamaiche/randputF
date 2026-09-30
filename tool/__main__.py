"""randputF external generator CLI."""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import yaml

from tool.common.db import VanillaDB
from tool.common.demo import build_demo_db
from tool.common.version import MOD_NAME_VERSIONED, VERSION
from tool.exporters.mod_seed import write_seed_files
from tool.exporters.seed_graph import write_seed_graph_html
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump, summarize_db
from tool.validator.solver import validate_seed

from tool.audit.tags import audit_building_tags, audit_item_tags, summarize_tags
from tool.audit.difficulty import compute_difficulty, summarize_difficulty

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
MOD_SOURCE = Path(__file__).resolve().parent.parent / "mod"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_db(demo: bool, dump_path: Path) -> VanillaDB:
    if demo:
        return build_demo_db()
    if not dump_path.exists():
        print(
            f"Vanilla dump introuvable: {dump_path}\n"
            "Genere-le avec le mod compagnon 'exporter' (voir README section Systeme de dev),\n"
            "ou lance la pipeline en mode demo: randputf generate --demo"
        )
        sys.exit(1)
    try:
        return load_db_from_dump(json.loads(dump_path.read_text(encoding="utf-8")))
    except ValueError as err:
        print(f"[DUMP INVALIDE] {err}")
        sys.exit(1)


def _build_mod(seed: dict, dest: Path) -> Path:
    """Assemble le mod complet dans dest. Retourne le chemin du dossier."""
    mod_name = MOD_NAME_VERSIONED
    mod_dir = dest / mod_name
    dest.mkdir(parents=True, exist_ok=True)

    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    mod_dir.mkdir()

    for item in MOD_SOURCE.iterdir():
        if item.name == "seed" or item.is_symlink():
            continue
        target = mod_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    write_seed_files(seed, mod_dir / "seed")
    return mod_dir


def _install_mod(seed: dict, mods_dir: Path) -> None:
    """Copie le mod dans le dossier Factorio mods + met a jour mod-list.json."""
    mod_name = MOD_NAME_VERSIONED
    dest = mods_dir / mod_name

    if dest.is_symlink():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)

    _build_mod(seed, mods_dir)

    info = json.loads((dest / "info.json").read_text(encoding="utf-8"))
    mod_list_name = info.get("name", mod_name)

    mod_list = mods_dir / "mod-list.json"
    if mod_list.exists():
        data = json.loads(mod_list.read_text(encoding="utf-8"))
    else:
        data = {"mods": [{"name": "base", "enabled": True}]}

    names = {m["name"] for m in data["mods"]}
    if mod_list_name not in names:
        data["mods"].append({"name": mod_list_name, "enabled": True})
    else:
        for m in data["mods"]:
            if m["name"] == mod_list_name:
                m["enabled"] = True
    for m in data["mods"]:
        if m["name"] == "randputf-exporter":
            m["enabled"] = False

    mod_list.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def cmd_parse(args: argparse.Namespace) -> None:
    """Chargement + résumé CLI de la base vanilla (dump ou demo)."""
    db = _load_db(args.demo, Path(args.dump))
    print(summarize_db(db))


def cmd_audit(args: argparse.Namespace) -> None:
    """Audit CLI des tags (bâtiments + items) ; exit 1 si violations."""
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


def cmd_generate(args: argparse.Namespace) -> None:
    """Génère une seed (démonstrateur) puis l'assemble en mod : seed.json/
    .lua + graphe HTML. Retente avec une graine dérivée tant que la seed est
    invalide (≤10 tentatives, sinon exit 2)."""
    db = _load_db(args.demo, Path(args.dump))
    cfg = _load_config()

    if args.seed is not None:
        db.seed_value = args.seed
    else:
        # Seed tirée du temps courant (ms) : partie unique à chaque génération.
        db.seed_value = int(time.time() * 1000)

    seed = generate_seed(db, config=cfg)

    # Une seed peut être non solvable : régénérer avec une graine dérivée.
    attempts = 0
    while validate_seed(seed):
        attempts += 1
        if attempts >= 10:
            for issue in validate_seed(seed)[:10]:
                print(f"[INVALIDE] {issue}")
            sys.exit(2)
        db.seed_value = int(time.time() * 1000) + attempts
        seed = generate_seed(db, config=cfg)

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
                print("Aucun dossier mods configure (paths.factorio_mods vide dans config/settings.yaml).")
            else:
                print(f"Dossier Factorio mods introuvable ({raw_path})")
            print(f"Seed {db.seed_value} valide, mod assemble dans {mod_path}")
            print("Copie-le manuellement dans ton dossier mods Factorio.")
    else:
        out_dir = Path(args.out) if args.out else OUTPUT_DIR
        zip_path = _build_mod(seed, out_dir)
        html_path = zip_path / "seed.graph.html"
        write_seed_graph_html(seed, html_path)
        print(f"Seed {db.seed_value} valide, mod assemblé dans {zip_path}")
        print(f"Graphe interactif (cliquable) exporté dans {html_path}")


def cmd_difficulty(args: argparse.Namespace) -> None:
    """Génère une seed et affiche son ardoise de difficulté (recettes
    primaires, DAG)."""
    db = _load_db(args.demo, Path(args.dump))
    db.seed_value = args.seed if args.seed is not None else int(time.time() * 1000)
    seed = generate_seed(db)
    report = compute_difficulty(seed)
    print(f"Ardoise de la seed {db.seed_value} (recettes primaires, DAG)")
    print(summarize_difficulty(report))


def main(argv: list[str] | None = None) -> None:
    """Point d'entrée CLI ``randputf`` (parse / audit / generate /
    difficulty)."""
    parser = argparse.ArgumentParser(prog="randputf", description="Generateur de seeds randputF")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Charge et resume la base vanilla")
    p_parse.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_parse.add_argument("--dump", default="data/vanilla_dump.json")
    p_parse.set_defaults(func=cmd_parse)

    p_audit = sub.add_parser("audit", help="Audite les tags de bâtiments (invariants C8)")
    p_audit.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_audit.add_argument("--dump", default="data/vanilla_dump.json")
    p_audit.set_defaults(func=cmd_audit)

    p_diff = sub.add_parser("difficulty", help="Ardoise de la seed : ressources brutes pour finir une run")
    p_diff.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_diff.add_argument("--dump", default="data/vanilla_dump.json")
    p_diff.add_argument("--seed", type=int, default=None,
                        help="Seed a imposer (defaut: tiree du temps courant en millisecondes)")
    p_diff.set_defaults(func=cmd_difficulty)

    p_gen = sub.add_parser("generate", help="Genere, valide puis exporte une seed dans le mod")
    p_gen.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_gen.add_argument("--dump", default="data/vanilla_dump.json")
    p_gen.add_argument("--out", default=None, help="Dossier de sortie (defaut: output/randputF_<version>)")
    p_gen.add_argument("--seed", type=int, default=None, help="Seed a imposer (defaut: tiree du temps courant en millisecondes)")
    p_gen.add_argument("--install", action="store_true", help="Installe le mod directement dans Factorio")
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
