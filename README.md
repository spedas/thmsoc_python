# thmsoc_python
Tools to be used for THEMIS SOC processing

Repo Organization

thmsoc_python uses the 'src' layout convention (see https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
Everything belongs to the 'thmsoc' module in src/thmsoc.  

Many of the tools are meant to be run as standalone scripts.   They will typically have one or
more Python files under src/thmsoc, then a CLI wrapper (to handle argument parsing, etc) under src/thmsoc/cli.
For example, see src/thmsoc/product_volume.py (bulk of implementation), and src/thmsoc/cli/product_volume.py (CLI wrapper).
Do not attempt to call the wrappers in src/thmsoc/cli directly; instead, make sure they get added
in pyproject.toml under `[project.scripts]`.  When the installer is run, it will create a small Python program
in .venv/bin with the appropriate shebang to invoke the correct Python version and script code.  
Running the .venv/bin activation script ensures that all the defined scripts will be on your $PATH.

For development and testing purposes, we recommend installing a personal copy of the repo.

The repo comes with a sample TOML file "example_thmsoc_python_config.toml", to set up paths and other configuration settings.
Copy this to "thmsoc_python_config.toml" in the top level directory, then edit the paths as desired.
For example, if you're testing on your laptop, you probably don't have /disks/themisdata available, 
but you probably have a SPEDAS data directory...use the 'themis' subdirectory as 'input_dataroot'.

If you're developing on one of the lab machines, you can read from /disks/themisdata, but 
won't be able to write to it.  If you're testing a script that would normally create output files
under /disks/themisdata, set 'output_dataroot' to someplace where you have write permission.

A complete bootstrap process for installing thmsoc_python for personal use would look like this:

1) Install a standalone 'uv' if you don't already have one on your path; make sure 'git' is also on your path
2) `git clone https://github.com/spedas/thmsoc_python.git` in your desired location and cd into the top level thmsoc_python directory,
3) Use your standalone uv to set up a Python virtual environment: `uv venv --python 3.12`
4) Activate the environment: `source /path/to/thmsoc_python/.venv/bin/activate.csh` (or whatever shell you're using)
5) Install dependencies: `uv sync`
6) Source the activation script again to pick up the .venv's uv that just got installed
7) Copy example_thmsoc_python_config.toml to thmsoc_python_config.toml and customize as needed
7) Create an editable install:  'uv pip install -e .`
8) See if it worked: try calling `product_volume 2026-01-01 2026-01-31` (or date range of your choice) and see if the report is generated correctly.

Alternate method using PyCharm (might be better for a laptop installation):  File->Project from Version Control, 
navigate to the thmsoc_python repo, then use PyCharm to set up the venv. Copy and customize thmsoc_python_config.toml.
Finally, open a PyCharm terminal window and do `uv pip install -e .` to make the editable install.


Deploying changes to production

After testing any local changes you want to make, push them out to the Github repo.
Then log into the 'thmsw' account on a RHEL machine (not ambrosia, unti it gets updated).
Activate the thmsoc_python venv:

`source /disks/socware/thmsoc_dp_current/thmsoc_python/.venv/activate.csh`

cd into the thmsoc_python directory and do 'git pull'.

`uv sync` to pick up any newly added dependencies

`uv pip install -e .` to install any new or modified CLI scripts.

If any changes were made to example_thmsoc_python_config.toml, propagate them to thmsoc_python_config.toml

When doing a `git pull` to update your personal installation, you should also use the above steps
to make sure your venv and local config are fully updated.






