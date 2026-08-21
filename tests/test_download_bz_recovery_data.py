import io
from pathlib import Path

import thmsoc.download_bz_recovery_data as downloader
from thmsoc.download_bz_recovery_data import (
    RemoteFile,
    destination_directory,
    download_files,
    list_remote_files,
    parse_share_url,
    recovery_type_from_name,
    requested_recovery_types,
)
from thmsoc.cli.download_bz_recovery_data import build_parser


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


def test_cli_defaults_to_fgs():
    args = build_parser().parse_args(["tha", "2025"])
    assert args.recovery_type == "fgs"


def test_cli_accepts_both():
    args = build_parser().parse_args(["tha", "2025", "--type", "both"])
    assert args.recovery_type == "both"


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
