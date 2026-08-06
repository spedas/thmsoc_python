Development and deployment
==========================

Repository layout
-----------------

The project uses the ``src`` layout. Core implementations live in
``src/thmsoc`` and command-line wrappers live in ``src/thmsoc/cli``. Register
new commands in ``pyproject.toml`` under ``[project.scripts]`` rather than
running wrapper modules directly.

Command-line parsers
--------------------

Each CLI module should expose a no-argument ``build_parser()`` function that
returns an :class:`argparse.ArgumentParser`. ``main()`` should parse that
object and run the command. This lets ``sphinx-argparse`` generate accurate
reference documentation without executing the command.

Building the documentation
--------------------------

Install the documentation dependency group and build with Sphinx::

   uv sync --group docs
   make -C docs html

Open ``docs/_build/html/index.html`` to inspect the result.

Production installation
-----------------------

The lab installation is an editable working copy at
``/disks/socware/thmsoc_dp_current/thmsoc_python`` owned by ``thmsw``. After
tested changes are merged, log in to ``thmsw`` on ambrosia, activate the
project environment, pull the changes, and refresh dependencies and entry
points::

   source /disks/socware/thmsoc_dp_current/thmsoc_python/.venv/bin/activate.csh
   cd /disks/socware/thmsoc_dp_current/thmsoc_python
   git pull
   uv sync --all-groups --all-extras
   uv pip install -e .

Propagate changes from ``example_thmsoc_python_config.toml`` to the production
configuration when necessary.

Documentation on readthedocs.io
--------------------------------

The documentation on thmsoc_python.readthedocs.io should rebuild automatically on every push to the main
branch.  If something there seems missing or malformed, try rebuilding it locally and checking the build log for
errors, or log into readthedocs.io, go to the thmsoc_python projects, and inspect their build logs.