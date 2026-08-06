Installation
============

Python 3.10 or newer is required. For a development or testing installation,
clone the repository and create a virtual environment with `uv`_::

   git clone https://github.com/spedas/thmsoc_python.git
   cd thmsoc_python
   uv venv --python 3.12
   source .venv/bin/activate
   uv sync
   uv pip install -e .

Copy ``example_thmsoc_python_config.toml`` to
``thmsoc_python_config.toml`` and adjust it before running tools that require
local paths. The editable install creates each command declared under
``[project.scripts]`` in the active environment.

.. _uv: https://docs.astral.sh/uv/getting-started/installation/
