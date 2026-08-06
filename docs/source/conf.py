"""Sphinx configuration for thmsoc-python."""

from importlib.metadata import PackageNotFoundError, version as package_version

project = "thmsoc-python"
author = "The THEMIS SOC team"
copyright = "The Regents of the University of California"

try:
    release = package_version("thmsoc-python")
except PackageNotFoundError:
    release = "unknown"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxarg.ext",
]

# CLI parser imports should not initialize PySPEDAS or its optional GUI/data
# stack during a documentation build.
autodoc_mock_imports = ["pyspedas"]

templates_path = ["_templates"]
exclude_patterns = []
html_theme = "sphinx_rtd_theme"


def setup(app):
    """Disable parallel reads until sphinx-argparse supports domain merging."""
    app.parallel = 1
