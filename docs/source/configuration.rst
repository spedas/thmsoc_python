Configuration
=============

The repository includes ``example_thmsoc_python_config.toml``. Copy it to
``thmsoc_python_config.toml`` at the repository root, then customize the input
and output paths for your environment.

On Windows, use forward slashes or doubled backslashes in TOML paths because a
single backslash begins an escape sequence. On the THEMIS lab machines,
``/disks/themisdata`` may be used for input, but development output should point
to a location where your account has write permission.
