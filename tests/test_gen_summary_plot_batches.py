import sys

import pytest

from thmsoc import config
from thmsoc.arguments import expand_probe_arguments
from thmsoc.cli.gen_summary_plot_batches import build_parser, main
from thmsoc.gen_summary_plot_batches import make_plot_batches


def test_flat_option_defaults_to_false():
    args = build_parser().parse_args(["--days", "1", "-t", "over", "-o", "/tmp"])

    assert args.flat is False


def test_plot_dir_option_defaults_to_configured_directory():
    args = build_parser().parse_args(["--days", "1", "-t", "over", "-o", "/tmp"])

    assert args.plot_dir is None


def test_plot_dir_option_accepts_user_supplied_directory():
    args = build_parser().parse_args(
        ["--days", "1", "-t", "over", "-o", "/tmp", "--plot_dir", "/plots"]
    )

    assert args.plot_dir == "/plots"


def test_probe_option_defaults_to_all_probes():
    args = build_parser().parse_args(["--days", "1", "-t", "over", "-o", "/tmp"])

    assert expand_probe_arguments(args) == ["a", "b", "c", "d", "e"]


def test_probe_option_accepts_selected_probes():
    args = build_parser().parse_args(
        ["--days", "1", "-t", "over", "-o", "/tmp", "-p", "a", "e"]
    )

    assert expand_probe_arguments(args) == ["a", "e"]


def test_make_plot_batches_accepts_custom_plot_dir_and_probes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "default_config_path", lambda: tmp_path / "missing.toml")
    make_plot_batches(
        start_date="2024-05-25",
        end_date=None,
        days=1,
        days_per_batch=1,
        summary_plot_types=["over"],
        probes=["a", "e"],
        output_directory=tmp_path,
        plot_dir="/custom/plots",
    )

    batch_contents = (tmp_path / "batch_2024-05-25.bm").read_text()
    assert ",/direct_to_dbase\n" in batch_contents
    assert "probes=['a', 'e']" in batch_contents
    assert "plot_dir='/custom/plots'" in batch_contents


@pytest.mark.parametrize("output_dataroot", ["/disks/themisdata", "/disks/themisdata/"])
def test_make_plot_batches_uses_production_defaults(tmp_path, monkeypatch, output_dataroot):
    config_path = tmp_path / "thmsoc_python_config.toml"
    config_path.write_text(f'[paths]\noutput_dataroot = "{output_dataroot}"\n')
    monkeypatch.setattr(config, "default_config_path", lambda: config_path)

    make_plot_batches(
        start_date="2024-05-25",
        end_date=None,
        days=1,
        days_per_batch=1,
        summary_plot_types=["over"],
        output_directory=tmp_path,
    )

    batch_contents = (tmp_path / "batch_2024-05-25.bm").read_text()
    assert ",/direct_to_dbase\n" in batch_contents
    assert "plot_dir='/disks/themisdata/overplots/'" in batch_contents
    assert "probes='all'" in batch_contents


def test_flat_cli_writes_batch_without_direct_to_dbase(tmp_path, monkeypatch):
    config_path = tmp_path / "thmsoc_python_config.toml"
    config_path.write_text('[paths]\noutput_dataroot = "/disks/themisdata/"\n')
    monkeypatch.setattr(config, "default_config_path", lambda: config_path)
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    monkeypatch.setattr(
        sys, "argv",
        [
            "gen_summary_plot_batches", "--start_date", "2024-05-25", "--days", "1",
            "-t", "over", "-o", str(tmp_path), "--flat",
        ],
    )

    assert main() == 0

    batch_contents = (tmp_path / "batch_2024-05-25.bm").read_text()
    assert "/direct_to_dbase" not in batch_contents
    assert "plot_dir='/disks/themisdata/overplots/'" in batch_contents
