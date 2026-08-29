from thmsoc.gen_l2_batches import make_l2_batches
from thmsoc.gen_scmode_batches import make_scmode_batches


def test_make_scmode_batches_uses_keyword_date_ranges(tmp_path):
    make_scmode_batches(
        start_date="2024-05-25",
        end_date="2024-05-29",
        days=None,
        days_per_batch=3,
        probes=["e"],
        output_directory=tmp_path,
    )

    first_batch = (tmp_path / "batch_2024-05-25_probe_e.bm").read_text()
    final_batch = (tmp_path / "batch_2024-05-28_probe_e.bm").read_text()

    assert first_batch == (
        "thm_scmode_reprocess_days,start_date='2024-05-25',"
        "end_date='2024-05-27',probes='e'\nexit\n"
    )
    assert final_batch == (
        "thm_scmode_reprocess_days,start_date='2024-05-28',"
        "end_date='2024-05-29',probes='e'\nexit\n"
    )


def test_make_l2_batches_uses_keyword_date_ranges(tmp_path):
    make_l2_batches(
        start_date="2024-05-25",
        end_date="2024-05-29",
        days=None,
        days_per_batch=3,
        l2_types=["fit", "fgm"],
        probes=["e"],
        output_directory=tmp_path,
    )

    first_batch = (tmp_path / "batch_2024-05-25_probe_e.bm").read_text()
    final_batch = (tmp_path / "batch_2024-05-28_probe_e.bm").read_text()

    assert first_batch == (
        "thm_reprocess_l2gen_days,start_date='2024-05-25',"
        "end_date='2024-05-27',instrument=['fit', 'fgm'],probes='e'\nexit\n"
    )
    assert final_batch == (
        "thm_reprocess_l2gen_days,start_date='2024-05-28',"
        "end_date='2024-05-29',instrument=['fit', 'fgm'],probes='e'\nexit\n"
    )
