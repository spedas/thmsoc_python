import argparse

from thmsoc.arguments import (
    add_l2_arguments,
    add_probe_arguments,
    add_summary_plot_arguments,
    expand_l2_arguments,
    expand_probe_arguments,
    expand_summary_plot_arguments,
    valid_l2_vals,
    valid_probe_vals,
    valid_summary_plot_vals,
)


def test_all_expands_to_only_valid_probes():
    parser = argparse.ArgumentParser()
    add_probe_arguments(parser)

    args = parser.parse_args(["--probes", "all"])

    assert expand_probe_arguments(args) == valid_probe_vals
    assert "all" not in expand_probe_arguments(args)


def test_all_expands_to_only_valid_l2_types():
    parser = argparse.ArgumentParser()
    add_l2_arguments(parser)

    args = parser.parse_args(["--l2_types", "all"])

    assert expand_l2_arguments(args) == valid_l2_vals
    assert "all" not in expand_l2_arguments(args)


def test_all_expands_to_only_valid_summary_plot_types():
    parser = argparse.ArgumentParser()
    add_summary_plot_arguments(parser)

    args = parser.parse_args(["--summary_plot_types", "all"])

    assert expand_summary_plot_arguments(args) == valid_summary_plot_vals
    assert "all" not in expand_summary_plot_arguments(args)
