from __future__ import annotations

import argparse
from pathlib import Path

from thmsoc.download_bz_recovery_data import DEFAULT_SHARE_URL, fetch_year


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download selected Bz recovery .sav files for a THEMIS probe and year, "
            "then install them in the production directory hierarchy."
        )
    )
    parser.add_argument("probe", choices=("tha", "thb", "thc", "thd", "the"))
    parser.add_argument("year", type=int)
    parser.add_argument(
        "--type",
        dest="recovery_type",
        choices=("fgl", "fgs", "both"),
        default="fgs",
        help="recovery file type to download (default: %(default)s)",
    )
    parser.add_argument(
        "--share-url",
        default=DEFAULT_SHARE_URL,
        help="Nextcloud public-share URL (default: %(default)s)",
    )
    parser.add_argument(
        "--dataroot",
        type=Path,
        help="override output_dataroot from thmsoc_python_config.toml",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    downloaded = fetch_year(
        args.probe,
        args.year,
        share_url=args.share_url,
        dataroot=args.dataroot,
        recovery_type=args.recovery_type,
    )
    print(f"Downloaded {len(downloaded)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
