from pathlib import Path

from thmsoc.download_bz_recovery_data import (
    destination_directory,
    parse_share_url,
    production_name,
)


def test_parse_share_url_ignores_directory_query():
    root, token = parse_share_url(
        "https://cloud.example/s/share-token?dir=/THA/2025"
    )
    assert root == "https://cloud.example/public.php/webdav/"
    assert token == "share-token"


def test_production_name_removes_probe_prefix():
    assert (
        production_name("tha_fgl_sensor_x_2025_01_01_2025_02_01.sav", "tha")
        == "fgl_sensor_x_2025_01_01_2025_02_01.sav"
    )


def test_destination_directory():
    assert destination_directory(Path("/data"), "tha", 2025) == Path(
        "/data/tha/l1b/fgm/sav_files/2025"
    )
