"""Launch IDL batch files listed in a master list."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

from .idl import IdlJob, Pathish, run_idl


def launch_idl_batches(
    batch_names: Iterable[str],
    directory: Pathish,
    *,
    config_path: Pathish | None = None,
) -> list[IdlJob]:
    """Launch listed batch files as detached jobs with colocated log files."""
    working_directory = Path(directory).resolve()
    jobs: list[IdlJob] = []

    for line in batch_names:
        batch_name = line.strip()
        if not batch_name:
            continue

        batch_path = Path(batch_name)
        if not batch_path.is_absolute():
            batch_path = working_directory / batch_path
        log_path = working_directory / f"{batch_path.name}.log"
        job = run_idl(
            batch_path,
            cwd=working_directory,
            stdin=subprocess.DEVNULL,
            stdout_path=log_path,
            stderr="stdout",
            config_path=config_path,
            wait=False,
            start_new_session=True,
        )
        if not isinstance(job, IdlJob):
            raise TypeError("asynchronous IDL launch did not return an IdlJob")
        jobs.append(job)

    return jobs
