"""randputF external generator CLI."""

import argparse
import json
import sys
import yaml
from pathlib import Path

from tool.common.db import VanillaDB
from tool.common.demo import build_demo_db
from tool.exporters.mod_seed import write_seed_files
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump, summarize_db
from tool.validator.solver import validate_seed

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_db(demo: bool, dump_path: Path) -> VanillaDB:
    if demo:
        return build_demo_db()
    if not dump_path.exists():
        print(
            f"Vanilla dump introuvable: {dump_path}\n"
            "Genere-le avec le mod compagnon 'exporter' (voir README section Mise en route),\n"
            "ou lance la pipeline en mode demo: randputf generate --demo"
        )
        sys.exit(1)
    return load_db_from_dump(json.loads(dump_path.read_text(encoding="utf-8")))


def cmd_parse(args: argparse.Namespace) -> None:
    db = _load_db(args.demo, Path(args.dump))
    print(summarize_db(db))


def cmd_generate(args: argparse.Namespace) -> None:
    db = _load_db(args.demo, Path(args.dump))

    if args.seed is not None:
        db.seed_value = args.seed
    else:
        cfg = _load_config()
        db.seed_value = cfg.get("seed", 0)

    seed = generate_seed(db)
    issues = validate_seed(seed)
    if issues:
        for issue in issues:
            print(f"[INVALIDE] {issue}")
        sys.exit(2)
    out_dir = Path(args.mod_dir) / "seed" if not args.out else Path(args.out)
    write_seed_files(seed, out_dir)
    print(summarize_db(db))
    print(f"Seed {db.seed_value} valide exportee vers {out_dir}/ (seed.json + seed.lua)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="randputf", description="Generateur de seeds randputF")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Charge et resume la base vanilla")
    p_parse.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_parse.add_argument("--dump", default="data/vanilla_dump.json")
    p_parse.set_defaults(func=cmd_parse)

    p_gen = sub.add_parser("generate", help="Genere, valide puis exporte une seed dans le mod")
    p_gen.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_gen.add_argument("--dump", default="data/vanilla_dump.json")
    p_gen.add_argument("--mod-dir", default="mod")
    p_gen.add_argument("--out", default=None, help="Dossier de sortie alternatif (defaut: mod/seed)")
    p_gen.add_argument("--seed", type=int, default=None, help="Seed (defaut: lit config/settings.yaml)")
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
