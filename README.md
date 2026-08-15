# thmsoc_python

Python tools used for THEMIS Science Operations Center processing.

The project uses the [`src` layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/). Core implementations live in `src/thmsoc`, command-line wrappers live in `src/thmsoc/cli`, and installed commands are declared in `pyproject.toml` under `[project.scripts]`. Supporting IDL procedures live in [`idl`](idl/README.md).

## Documentation

The documentation covers installation, configuration, development and deployment, and all available command-line tools:

- [thmsoc-python documentation](https://thmsoc-python.readthedocs.io)
- [Documentation source](docs/source/index.rst)

To build it locally:

```console
uv sync --all-groups --all-extras
make -C docs html
```

## Quick start

```console
git clone https://github.com/spedas/thmsoc_python.git
cd thmsoc_python
uv venv --python 3.12
source .venv/bin/activate
uv sync --all-groups --all-extras
uv pip install -e .
cp example_thmsoc_python_config.toml thmsoc_python_config.toml
```

Customize `thmsoc_python_config.toml` for your environment, then run an installed command. For example:

```console
product_volume -s 2026-01-01 -e 2026-01-31
```

See the [installation guide](docs/source/installation.rst) for details.
