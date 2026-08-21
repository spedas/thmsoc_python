import io
import subprocess
import urllib.error
from datetime import date
from pathlib import Path

import thmsoc.download_bz_recovery_data as downloader
import thmsoc.cli.download_bz_recovery_data as cli
from thmsoc.download_bz_recovery_data import (
    RemoteFile,
    destination_directory,
    download_files,
    list_remote_files,
    parse_share_url,
    recovery_type_from_name,
    requested_recovery_types,
)
from thmsoc.cli.download_bz_recovery_data import (
    build_parser,
    process_batch_source,
    process_downloads,
    resolve_directories,
)


def test_parse_share_url_ignores_directory_query():
    root, token = parse_share_url(
        "https://cloud.example/s/share-token?dir=/THA/2025"
    )
    assert root == "https://cloud.example/public.php/webdav/"
    assert token == "share-token"


def test_recovery_type_from_probe_prefixed_name():
    name = "tha_fgl_sensor_x_2025_01_01_2025_02_01.sav"
    assert recovery_type_from_name(name, "tha") == "fgl"


def test_recovery_type_from_unprefixed_name():
    name = "fgl_sensor_x_2026_01_01_2026_02_01.sav"
    assert recovery_type_from_name(name, "the") == "fgl"


def test_recovery_type_rejects_different_probe_prefix():
    name = "tha_fgs_sensor_x_2025_01_01_2025_02_01.sav"
    assert recovery_type_from_name(name, "the") is None


def test_requested_recovery_types():
    assert requested_recovery_types("fgl") == {"fgl"}
    assert requested_recovery_types("fgs") == {"fgs"}
    assert requested_recovery_types("both") == {"fgl", "fgs"}


def test_cli_requires_and_accepts_multiple_probes_and_years():
    args = build_parser().parse_args(
        ["--probes", "tha", "the", "--years", "2024", "2025"]
    )
    assert args.probes == ["tha", "the"]
    assert args.years == [2024, 2025]
    assert args.recovery_type == "fgl"


def test_cli_accepts_fgs_and_processing_options(tmp_path):
    args = build_parser().parse_args(
        [
            "--probes", "the", "--years", "2025", "--type", "fgs",
            "--process-downloads", "--reprocess",
            "--download-directory", str(tmp_path / "downloads"),
            "--production-directory", str(tmp_path / "production"),
            "--working-directory", str(tmp_path / "working"),
            "--temp-directory", str(tmp_path / "temp"),
        ]
    )
    assert args.recovery_type == "fgs"
    assert args.process_downloads
    assert args.reprocess


def test_resolve_directories_uses_config_and_start_date(monkeypatch):
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: {"paths": {"temproot": "/tmp/root", "output_dataroot": "/data"}},
    )
    args = build_parser().parse_args(
        ["--probes", "the", "--years", "2025", "--process-downloads"]
    )

    resolve_directories(args, date(2026, 8, 21))

    assert args.download_directory == Path("/tmp/root/bz_recovery_download_20260821")
    assert args.production_directory == Path("/data")
    assert args.working_directory == Path(
        "/tmp/root/bz_recovery_working_directory_20260821"
    )
    assert args.temp_directory == Path("/tmp/root/bz_recovery_tempdir_20260821")


def test_process_batch_source_maps_probes_paths_and_reprocess(tmp_path):
    args = build_parser().parse_args(
        [
            "--probes", "tha", "the", "--years", "2025", "--type", "fgs",
            "--process-downloads", "--reprocess",
            "--download-directory", str(tmp_path / "downloads"),
            "--production-directory", str(tmp_path / "production"),
            "--working-directory", str(tmp_path / "working"),
            "--temp-directory", str(tmp_path / "temp"),
        ]
    )

    source = process_batch_source(args)

    assert "probes=['a', 'e']" in source
    assert f"input_dataroot='{tmp_path / 'downloads'}'" in source
    assert f"output_dataroot='{tmp_path / 'production'}'" in source
    assert f"workdir='{tmp_path / 'working'}'" in source
    assert f"tmpdir='{tmp_path / 'temp'}'" in source
    assert "type_to_process='fgs'" in source
    assert source.endswith(", /reprocess\nexit\n")


def test_process_downloads_requires_success_status(monkeypatch, tmp_path):
    args = build_parser().parse_args(
        [
            "--probes", "the", "--years", "2025", "--process-downloads",
            "--download-directory", str(tmp_path / "downloads"),
            "--production-directory", str(tmp_path / "production"),
            "--working-directory", str(tmp_path / "working"),
            "--temp-directory", str(tmp_path / "temp"),
        ]
    )

    def fake_run_idl(batch_path, **kwargs):
        assert kwargs["stdin"] == subprocess.DEVNULL
        (kwargs["cwd"] / "status").write_text("Success\n", encoding="utf-8")
        return subprocess.CompletedProcess(["idl", str(batch_path)], 0)

    monkeypatch.setattr(cli, "run_idl", fake_run_idl)

    assert process_downloads(args)
    assert (args.working_directory / "process_bz_downloads.bm").is_file()


def test_process_downloads_rejects_failure_status(monkeypatch, tmp_path):
    args = build_parser().parse_args(
        [
            "--probes", "the", "--years", "2025", "--process-downloads",
            "--download-directory", str(tmp_path / "downloads"),
            "--production-directory", str(tmp_path / "production"),
            "--working-directory", str(tmp_path / "working"),
            "--temp-directory", str(tmp_path / "temp"),
        ]
    )

    def fake_run_idl(batch_path, **kwargs):
        (kwargs["cwd"] / "status").write_text("Failure\n", encoding="utf-8")
        return subprocess.CompletedProcess(["idl", str(batch_path)], 0)

    monkeypatch.setattr(cli, "run_idl", fake_run_idl)
    assert not process_downloads(args)


def test_main_downloads_cartesian_product_and_skips_unavailable(monkeypatch, tmp_path):
    calls = []

    def fake_fetch(probe, year, **kwargs):
        calls.append((probe, year, kwargs))
        if (probe, year) == ("tha", 2024):
            raise FileNotFoundError("not present")
        if (probe, year) == ("the", 2024):
            raise urllib.error.HTTPError("url", 404, "missing", {}, None)
        return [tmp_path / f"{probe}-{year}.sav"]

    monkeypatch.setattr(cli, "fetch_year", fake_fetch)
    result = cli.main(
        [
            "--probes", "tha", "the", "--years", "2024", "2025",
            "--type", "fgs", "--download-directory", str(tmp_path),
        ]
    )

    assert result == 0
    assert [(probe, year) for probe, year, _ in calls] == [
        ("tha", 2024), ("tha", 2025), ("the", 2024), ("the", 2025)
    ]
    assert all(call[2]["dataroot"] == tmp_path for call in calls)


def test_download_preserves_remote_filename(monkeypatch, tmp_path):
    content = b"recovery data"
    remote = RemoteFile(
        "tha_fgs_sensor_x_2025_01_01_2025_02_01.sav",
        "https://cloud.example/file.sav",
        len(content),
    )
    monkeypatch.setattr(downloader, "_request", lambda *args, **kwargs: io.BytesIO(content))

    downloaded = download_files([remote], "token", "", tmp_path)

    assert downloaded == [tmp_path / remote.name]
    assert downloaded[0].read_bytes() == content


def test_list_remote_files_filters_type_and_defaults_to_fgs(monkeypatch):
    listing = b"""<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:">
      <d:response><d:href>/public.php/webdav/THA/2025/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
      <d:response><d:href>/public.php/webdav/THA/2025/tha_fgl_sensor_x_2025_01_01_2025_02_01.sav</d:href><d:propstat><d:prop><d:resourcetype/><d:getcontentlength>10</d:getcontentlength></d:prop></d:propstat></d:response>
      <d:response><d:href>/public.php/webdav/THA/2025/tha_fgs_sensor_x_2025_01_01_2025_02_01.sav</d:href><d:propstat><d:prop><d:resourcetype/><d:getcontentlength>20</d:getcontentlength></d:prop></d:propstat></d:response>
    </d:multistatus>"""
    monkeypatch.setattr(
        downloader, "_request", lambda *args, **kwargs: io.BytesIO(listing)
    )

    default_files = list_remote_files("https://cloud.example/", "token", "", "tha", 2025)
    both_files = list_remote_files(
        "https://cloud.example/", "token", "", "tha", 2025, "both"
    )

    assert [remote.name for remote in default_files] == [
        "tha_fgs_sensor_x_2025_01_01_2025_02_01.sav"
    ]
    assert [remote.name for remote in both_files] == [
        "tha_fgl_sensor_x_2025_01_01_2025_02_01.sav",
        "tha_fgs_sensor_x_2025_01_01_2025_02_01.sav",
    ]


def test_destination_directory():
    assert destination_directory(Path("/data"), "tha", 2025) == Path(
        "/data/tha/l1b/fgm/sav_files/2025"
    )
