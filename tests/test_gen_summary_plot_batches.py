from thmsoc.cli.gen_summary_plot_batches import build_parser
from thmsoc.gen_summary_plot_batches import make_plot_batches


def test_install_option_defaults_to_false():
    args = build_parser().parse_args(["--days", "1", "-t", "over", "-o", "/tmp"])

    assert args.install is False


def test_install_option_accepts_short_and_long_flags():
    common_args = ["--days", "1", "-t", "over", "-o", "/tmp"]

    assert build_parser().parse_args([*common_args, "-i"]).install is True
    assert build_parser().parse_args([*common_args, "--install"]).install is True


def test_make_plot_batches_adds_direct_to_dbase_when_installing(tmp_path):
    make_plot_batches(
        start_date="2024-05-25",
        end_date=None,
        days=1,
        days_per_batch=1,
        summary_plot_types=["over"],
        output_directory=tmp_path,
        install=True,
    )

    batch_contents = (tmp_path / "batch_2024-05-25.bm").read_text()
    assert ",/direct_to_dbase\n" in batch_contents
    assert "plot_dir=" not in batch_contents


def test_make_plot_batches_omits_direct_to_dbase_by_default(tmp_path):
    make_plot_batches(
        start_date="2024-05-25",
        end_date=None,
        days=1,
        days_per_batch=1,
        summary_plot_types=["over"],
        output_directory=tmp_path,
    )

    batch_contents = (tmp_path / "batch_2024-05-25.bm").read_text()
    assert "/direct_to_dbase" not in batch_contents
    assert "plot_dir='/mydisks/home/thmsoc/summary_reprocess/'" in batch_contents
