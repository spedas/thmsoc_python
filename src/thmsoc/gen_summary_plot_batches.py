from pyspedas import time_string, time_double
from thmsoc import args_to_startend, batch_daterange, datelist_to_string
from pathlib import Path

from thmsoc.config import load_config


def _default_plot_dir():
    paths = load_config().get("paths", {})
    output_dataroot = paths.get("output_dataroot") if isinstance(paths, dict) else None
    if not isinstance(output_dataroot, str) or not output_dataroot.strip():
        raise ValueError("Set paths.output_dataroot in thmsoc_python_config.toml or supply --plot_dir")
    return f"{Path(output_dataroot) / 'overplots'}/"


def make_plot_batches(
    start_date,
    end_date,
    days,
    days_per_batch,
    summary_plot_types,
    output_directory,
    install=True,
    plot_dir=None,
    probes="all",
):
    """Generate IDL batches for dated plot directories, or a flat directory if install=False."""
    start, end = args_to_startend(start_date, end_date, days)
    if plot_dir is None:
        plot_dir = _default_plot_dir()
    plot_dir_literal = str(plot_dir).replace("'", "''")
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    master_list_path = output_path / "master_list.txt"
    with open(master_list_path, 'w') as m:
        for batch in batch_daterange(start, end, days_per_batch):
            batch_strings = datelist_to_string(batch)
            basename = f"batch_{batch_strings[0]}.bm"
            batch_filename_path = output_path/basename
            with open(batch_filename_path,'w') as f:
                probes_argument = f"'{probes}'" if isinstance(probes, str) else str(probes)
                output_keywords = f",probes={probes_argument},plot_dir='{plot_dir_literal}'"
                if install:
                    output_keywords += ",/direct_to_dbase"
                f.write(f"thm_over_shell,start_date='{batch_strings[0]}', end_date='{batch_strings[-1]}',inst={summary_plot_types}{output_keywords}\n")
                f.write(f"exit\n",)
            m.write(f"{basename}\n")

if __name__ == "__main__":
    make_plot_batches('2024-05-25','2026-03-15',7, days_per_batch=14, summary_plot_types=['over','fgmdyn'], output_directory='/tmp/gen_l2_batches')
