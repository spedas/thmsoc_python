"""Command-line interface for launching IDL batch master lists."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, TextIO

from thmsoc.launch_idl_batches import launch_idl_batches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch IDL batch files as detached background jobs."
    )
    parser.add_argument(
        "master_list",
        nargs="?",
        help="Master list file (default: standard input; use - explicitly for stdin)",
    )
    parser.add_argument(
        "--config",
        help="Path to the thmsoc_python TOML configuration file",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, stdin: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_stream = stdin if stdin is not None else sys.stdin

    if args.master_list is None or args.master_list == "-":
        directory = Path.cwd()
        jobs = launch_idl_batches(
            input_stream, directory, config_path=args.config
        )
    else:
        master_list_path = Path(args.master_list).resolve()
        with master_list_path.open(encoding="utf-8") as master_list:
            jobs = launch_idl_batches(
                master_list,
                master_list_path.parent,
                config_path=args.config,
            )

    for job in jobs:
        print(f"Launched {job.batch_path.name} (PID {job.process.pid})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
