from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
from datetime import date
from pathlib import Path
from typing import Sequence

from thmsoc.config import load_config
from thmsoc.download_bz_recovery_data import DEFAULT_SHARE_URL, fetch_year
from thmsoc.idl import run_idl

PROBES = ("tha", "thb", "thc", "thd", "the")
STATUS_SUCCESS = "Success"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download selected Bz recovery .sav files for one or more THEMIS "
            "probes and years, optionally processing them with IDL."
        )
    )
    parser.add_argument(
        "--probes", nargs="+", required=True, choices=PROBES,
        help="THEMIS probes to download (for example: --probes tha the)",
    )
    parser.add_argument(
        "--years", nargs="+", required=True, type=int,
        help="years to download (for example: --years 2024 2025)",
    )
    parser.add_argument(
        "--type",
        dest="recovery_type",
        choices=("fgl", "fgs"),
        default="fgl",
        help="recovery file type to download and process (default: %(default)s)",
    )
    parser.add_argument(
        "--share-url",
        default=DEFAULT_SHARE_URL,
        help="Nextcloud public-share URL (default: %(default)s)",
    )
    parser.add_argument(
        "--download-directory", type=Path,
        help="download root (default: TEMPROOT/bz_recovery_download_YYYYMMDD)",
    )
    parser.add_argument(
        "--process-downloads", action="store_true",
        help="run the IDL process_bz_downloads routine after downloading",
    )
    parser.add_argument(
        "--production-directory", type=Path,
        help="production root (default: output_dataroot from configuration)",
    )
    parser.add_argument(
        "--working-directory", type=Path,
        help="IDL working root (default: TEMPROOT/bz_recovery_working_directory_YYYYMMDD)",
    )
    parser.add_argument(
        "--temp-directory", type=Path,
        help="IDL temporary root (default: TEMPROOT/bz_recovery_tempdir_YYYYMMDD)",
    )
    parser.add_argument(
        "--reprocess", action="store_true",
        help="process downloads even when already installed in production",
    )
    return parser


def _configured_path(config: dict, name: str) -> Path:
    paths = config.get("paths", {})
    value = paths.get(name) if isinstance(paths, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"paths.{name} is required in thmsoc_python_config.toml")
    return Path(value)


def resolve_directories(args: argparse.Namespace, started: date) -> None:
    """Populate directory arguments from configuration and the start date."""
    config = load_config()
    suffix = started.strftime("%Y%m%d")
    if args.download_directory is None:
        args.download_directory = (
            _configured_path(config, "temproot") / f"bz_recovery_download_{suffix}"
        )
    if not args.process_downloads:
        return
    if args.production_directory is None:
        args.production_directory = _configured_path(config, "output_dataroot")
    temproot = None
    if args.working_directory is None or args.temp_directory is None:
        temproot = _configured_path(config, "temproot")
    if args.working_directory is None:
        args.working_directory = temproot / f"bz_recovery_working_directory_{suffix}"
    if args.temp_directory is None:
        args.temp_directory = temproot / f"bz_recovery_tempdir_{suffix}"


def _idl_quote(value: str | Path) -> str:
    """Return an IDL single-quoted string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def process_batch_source(args: argparse.Namespace) -> str:
    probes = ", ".join(_idl_quote(probe[-1]) for probe in args.probes)
    keywords = [
        f"probes=[{probes}]",
        f"input_dataroot={_idl_quote(args.download_directory)}",
        f"output_dataroot={_idl_quote(args.production_directory)}",
        f"workdir={_idl_quote(args.working_directory)}",
        f"tmpdir={_idl_quote(args.temp_directory)}",
        f"type_to_process={_idl_quote(args.recovery_type)}",
    ]
    if args.reprocess:
        keywords.append("/reprocess")
    return "process_bz_downloads, " + ", ".join(keywords) + "\nexit\n"


def process_downloads(args: argparse.Namespace) -> bool:
    """Run process_bz_downloads and validate its status file."""
    working_directory = args.working_directory
    working_directory.mkdir(parents=True, exist_ok=True)
    args.temp_directory.mkdir(parents=True, exist_ok=True)
    status_path = working_directory / "status"
    status_path.unlink(missing_ok=True)
    batch_path = working_directory / "process_bz_downloads.bm"
    batch_path.write_text(process_batch_source(args), encoding="utf-8")
    stdout_path = working_directory / "process_bz_downloads.stdout.log"
    stderr_path = working_directory / "process_bz_downloads.stderr.log"

    completed = run_idl(
        batch_path,
        cwd=working_directory,
        stdin=subprocess.DEVNULL,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    if completed.returncode:
        print(f"IDL process_bz_downloads exited with status {completed.returncode}.")
        return False
    try:
        status = status_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"IDL process_bz_downloads did not produce a readable status file: {exc}")
        return False
    if status != STATUS_SUCCESS:
        print(f"IDL process_bz_downloads reported {status or 'an empty status'}.")
        return False
    print("IDL process_bz_downloads completed successfully.")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(line_buffering=True)
    started = date.today()
    args = build_parser().parse_args(argv)
    try:
        resolve_directories(args, started)
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2

    downloaded_count = 0
    unavailable_count = 0
    for probe in args.probes:
        for year in args.years:
            try:
                downloaded = fetch_year(
                    probe,
                    year,
                    share_url=args.share_url,
                    dataroot=args.download_directory,
                    recovery_type=args.recovery_type,
                )
            except FileNotFoundError as exc:
                unavailable_count += 1
                print(f"Skipping unavailable {probe}/{year}: {exc}")
                continue
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                unavailable_count += 1
                print(f"Skipping unavailable {probe}/{year}: HTTP 404")
                continue
            downloaded_count += len(downloaded)

    print(
        f"Downloaded {downloaded_count} files; "
        f"{unavailable_count} probe/year combinations unavailable."
    )
    if args.process_downloads:
        try:
            if not process_downloads(args):
                return 1
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Unable to run IDL process_bz_downloads: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
