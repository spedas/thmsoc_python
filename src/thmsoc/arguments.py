import argparse

# Standard arguments for specifing time ranges
def add_trange_arguments(p:argparse.ArgumentParser) -> None:
    p.add_argument("-s", "--start_date", help="start date (YYYY-MM-DD)", default=None)
    p.add_argument("-e","--end_date", help="end date (YYYY-MM-DD)", default=None)
    p.add_argument("-d","--days", help="Duration (days)", type=int, default=None)

# Sanity checks on time range arguments
def check_trange_arguments(args:argparse.Namespace) -> bool:
    # check argument count
    count=0
    if args.start_date is not None:
        count+=1
    if args.end_date is not None:
        count+=1
    if args.days is not None:
        count +=1
    if count < 2:
        raise ValueError("At least two of start_date, end_date, or days must be specified")
    if args.days is not None and args.days < 1:
        raise ValueError("days must be positive")
    return True

valid_probe_vals = ['a', 'b', 'c', 'd', 'e']
valid_probe_args = valid_probe_vals
valid_probe_args.append('all')

valid_summary_plot_vals = ['over', 'esa', 'fgm', 'sst', 'memory', 'fitmom', 'fitgmom', 'fftfbk', 'fgmdyn']
valid_summary_plot_args = valid_summary_plot_vals
valid_summary_plot_args.append('all')

valid_l2_vals = ['fgm','fbk','fit','esa', 'mom','gmom','sst', 'fft', 'scm', 'efi','efp', 'efw', 'scmode']
valid_l2_args = valid_l2_vals
valid_l2_args.append('all')

def add_probe_arguments(p:argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--probes", help="Probes to process", required=True, nargs='*', choices=valid_probe_args)

def expand_probe_arguments(args:argparse.Namespace) -> list[str]:
    if 'all' in args.probes:
        return valid_probe_vals
    else:
        return args.probes

def add_summary_plot_arguments(p:argparse.ArgumentParser) -> None:
    p.add_argument("-t", "--summary_plot_types", help="Plots to create", required=True, nargs='*', choices=valid_summary_plot_args)

def expand_summary_plot_arguments(args:argparse.Namespace) -> list[str]:
    if 'all' in args.summary_plot_types:
        return valid_summary_plot_vals
    else:
        return args.summary_plot_types

def add_l2_arguments(p:argparse.ArgumentParser) -> None:
    p.add_argument("-t", "--l2_types", help="L2 files to create", required=True, nargs='*', choices=valid_l2_args)

def expand_l2_arguments(args:argparse.Namespace) -> list[str]:
    if 'all' in args.l2_types:
        return valid_l2_vals
    else:
        return args.l2_types
