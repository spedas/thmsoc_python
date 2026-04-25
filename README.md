# thmsoc_python
Tools to be used for THEMIS SOC processing

## Repo Organization

thmsoc_python uses the 'src' layout convention (see https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
Everything belongs to the 'thmsoc' module in src/thmsoc.  

Many of the tools are meant to be run as standalone scripts.   They will typically have one or
more Python files under src/thmsoc, then a CLI wrapper (to handle argument parsing, etc) under src/thmsoc/cli.
For example, see src/thmsoc/product_volume.py (bulk of implementation), and src/thmsoc/cli/product_volume.py (CLI wrapper).
Do not attempt to call the wrappers in src/thmsoc/cli directly; instead, make sure they get added
in pyproject.toml under `[project.scripts]`.  When the installer is run, it will create a small Python program
in .venv/bin, with the appropriate shebang to invoke the correct Python version and script code.  
Running the .venv/bin activation script ensures that all the defined scripts will be on your $PATH.

## Production installation

thmsoc_python is installed on the lab machines under /disks/socware/thmsoc_dp_current/thmsoc_python .
It's a git working copy and editable installation, owned by the thmsw user (just like the production IDL code, ksh scripts, etc.)
It has a dedicated Python virtual environment (currently set up with python 3.12) in thmsoc_python/.venv . 
The installation was done on one of our RHEL servers, so the tools may not work on ambrosia until that
machine is upgraded to RHEL.


## Development and testing installations

For development and testing purposes, we recommend installing a personal copy of the repo.

The repo comes with a sample TOML file "example_thmsoc_python_config.toml", to set up paths and other configuration settings.
Copy this to "thmsoc_python_config.toml" in the top level directory, then edit the paths as desired.
For example, if you're testing on your laptop, you probably don't have /disks/themisdata available, 
but you probably have a SPEDAS data directory...use the 'themis' subdirectory as 'input_dataroot'.

Note for Windows users:  TOML parsers interpret a single '\\' as an escape character.  To avoid this issue when specifying Windows
paths, you can use forward slash characters '/', or double backslashes, '\\\\', to separate path components.

If you're developing on one of the lab machines, you can read from /disks/themisdata, but 
won't be able to write to it unless you're logged in as 'thmsoc' (not recommended for testing!).  

If you're testing a script that would normally create output files under /disks/themisdata, set 'output_dataroot' to someplace where you have write permission.

A complete bootstrap process for installing thmsoc_python for personal use would look like this:

1) Install a standalone 'uv' if you don't already have one on your path; make sure 'git' is also on your path (https://docs.astral.sh/uv/getting-started/installation/)
2) `git clone https://github.com/spedas/thmsoc_python.git` in your desired location and cd into the top level thmsoc_python directory,
3) Use your standalone uv to set up a Python virtual environment: `uv venv --python 3.12`
4) Activate the environment: `source /path/to/thmsoc_python/.venv/bin/activate.csh` (or whatever shell you're using)
5) Install dependencies: `uv sync`
6) Source the activation script again to pick up the .venv's uv that just got installed
7) Copy example_thmsoc_python_config.toml to thmsoc_python_config.toml and customize as needed
7) Create an editable install:  `uv pip install -e .`
8) See if it worked: try calling `product_volume -s 2026-01-01 -e 2026-01-31` (or date range of your choice) and see if the report is generated correctly.

Alternate method using PyCharm (might be better for a laptop installation):  File->Project from Version Control, 
navigate to the thmsoc_python repo, then use PyCharm to set up the venv. Copy and customize thmsoc_python_config.toml.
Finally, open a PyCharm terminal window and do `uv pip install -e .` to make the editable install.


## Updating the production installation

After testing any local changes you want to make, push them out to the Github repo.
Then log into the 'thmsw' account on a RHEL machine (not ambrosia, unti it gets updated).
Activate the thmsoc_python venv:

`source /disks/socware/thmsoc_dp_current/thmsoc_python/.venv/bin/activate.csh`

cd into the thmsoc_python directory and do `git pull`.

`uv sync` to pick up any newly added dependencies

`uv pip install -e .` to install any new or modified CLI scripts.

If any changes were made to example_thmsoc_python_config.toml, propagate them to thmsoc_python_config.toml

When doing a `git pull` to update your personal installation, you should also use the above steps
to make sure your venv and local config are fully updated.

## Available scripts

So far, we have:

product_volume:  Create a report of data volume in various categories over a time range.

```
usage: product_volume [-h] [-s START_DATE] [-e END_DATE] [-d DAYS]

options:
  -h, --help            show this help message and exit
  -s START_DATE, --start_date START_DATE
                        start date (YYYY-MM-DD)
  -e END_DATE, --end_date END_DATE
                        end date (YYYY-MM-DD)
  -d DAYS, --days DAYS  Duration (days)
```

gen_summary_plot_batches:  Create a master list and a set of IDL .bm batch files for processing summary plots

```
usage: gen_summary_plot_batches [-h] [-s START_DATE] [-e END_DATE] [-d DAYS] -t [{over,esa,fgm,sst,memory,fitmom,fitgmom,fftfbk,fgmdyn,all} ...] [-b BATCH_DAYS] -o
                                OUTPUT_DIRECTORY

options:
  -h, --help            show this help message and exit
  -s START_DATE, --start_date START_DATE
                        start date (YYYY-MM-DD)
  -e END_DATE, --end_date END_DATE
                        end date (YYYY-MM-DD)
  -d DAYS, --days DAYS  Duration (days)
  -t [{over,esa,fgm,sst,memory,fitmom,fitgmom,fftfbk,fgmdyn,all} ...], --summary_plot_types [{over,esa,fgm,sst,memory,fitmom,fitgmom,fftfbk,fgmdyn,all} ...]
                        Plots to create
  -b BATCH_DAYS, --batch_days BATCH_DAYS
                        Days per batch to process
  -o OUTPUT_DIRECTORY, --output_directory OUTPUT_DIRECTORY
                        Directory where master list and batch files will be written
```

gen_l2_batches: Create a master list and a set of IDL .bm batch files for processing L2 products

```
usage: gen_l2_batches [-h] [-s START_DATE] [-e END_DATE] [-d DAYS] -t [{fgm,fbk,fit,esa,mom,gmom,sst,fft,scm,efi,efp,efw,scmode,all} ...] -p [{a,b,c,d,e,all} ...]
                      [-b BATCH_DAYS] -o OUTPUT_DIRECTORY

options:
  -h, --help            show this help message and exit
  -s START_DATE, --start_date START_DATE
                        start date (YYYY-MM-DD)
  -e END_DATE, --end_date END_DATE
                        end date (YYYY-MM-DD)
  -d DAYS, --days DAYS  Duration (days)
  -t [{fgm,fbk,fit,esa,mom,gmom,sst,fft,scm,efi,efp,efw,scmode,all} ...], --l2_types [{fgm,fbk,fit,esa,mom,gmom,sst,fft,scm,efi,efp,efw,scmode,all} ...]
                        L2 files to create
  -p [{a,b,c,d,e,all} ...], --probes [{a,b,c,d,e,all} ...]
                        Probes to process
  -b BATCH_DAYS, --batch_days BATCH_DAYS
                        Days per batch to process
  -o OUTPUT_DIRECTORY, --output_directory OUTPUT_DIRECTORY
                        Directory where master list and batch files will be written
```

## Standard argument processing

thmsoc_python uses the argparse library to support consistent, reusable argument naming and handling 
across the various utilities. See src/thmsoc/arguments.py and the CLI script files for implementation details.

### Time range specification

```
  -s START_DATE, --start_date START_DATE
                        start date (YYYY-MM-DD)
  -e END_DATE, --end_date END_DATE
                        end date (YYYY-MM-DD)
  -d DAYS, --days DAYS  Duration (days)
```

Any two of these options suffice to define a time range: explicit start and end dates, or a start date
and duration, or an end date and duration.  The end date is included in the processing to be performed.

### Batching

```
  -b BATCH_DAYS, --batch_days BATCH_DAYS
                        Days per batch to process
```

### Probe specification

```
  -p [{a,b,c,d,e,all} ...], --probes [{a,b,c,d,e,all} ...]
                        Probes to process
```







