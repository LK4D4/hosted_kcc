from __future__ import annotations

import argparse
from pathlib import Path

from hosted_kcc.config import ConfigError, load_config
from hosted_kcc.service import configure_logging, run_forever, scan_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hosted-kcc",
        description="Watched-folder service for Kindle Comic Converter",
    )
    parser.add_argument(
        "--config",
        default="/config/config.toml",
        help="Path to config.toml. Missing files are generated from defaults/env.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scan/conversion pass and exit.",
    )
    parser.add_argument(
        "--kcc-command",
        default="c2e",
        help="KCC executable to run. Defaults to c2e from the KCC container image.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cfg = load_config(Path(args.config))
    except ConfigError as exc:
        parser.error(str(exc))
    configure_logging(cfg.logging.level)
    if args.once:
        result = scan_once(cfg, kcc_command=args.kcc_command)
        return 1 if result.failed else 0
    run_forever(cfg, kcc_command=args.kcc_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
