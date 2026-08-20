"""Launch IDL batch jobs in a configured THEMIS SOC environment."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Mapping, Sequence

from .config import load_config

Pathish = str | os.PathLike[str]
Redirect = Pathish | IO[Any] | int | None


@dataclass(frozen=True)
class IdlConfig:
    """IDL settings read from ``thmsoc_python_config.toml``."""

    executable: str = "idl"
    startup: Path | None = None
    path: tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)


def load_idl_config(config_path: Pathish | None = None) -> IdlConfig:
    """Load IDL paths and environment variables from the project config."""
    config = load_config(config_path)
    idl = config.get("idl", {})
    environment = config.get("environment", {})
    if not isinstance(idl, dict) or not isinstance(environment, dict):
        raise ValueError("[idl] and [environment] must be TOML tables")

    path = idl.get("path", [])
    if not isinstance(path, list) or not all(isinstance(item, str) for item in path):
        raise ValueError("idl.path must be an array of strings")
    if not all(isinstance(key, str) and isinstance(value, str)
               for key, value in environment.items()):
        raise ValueError("[environment] values must be strings")

    startup_value = idl.get("startup")
    if startup_value is not None and not isinstance(startup_value, str):
        raise ValueError("idl.startup must be a string")
    executable = idl.get("executable", "idl")
    if not isinstance(executable, str):
        raise ValueError("idl.executable must be a string")

    return IdlConfig(
        executable=executable,
        startup=Path(startup_value) if startup_value else None,
        path=tuple(path),
        environment=dict(environment),
    )


@dataclass
class IdlJob:
    """A running asynchronous IDL job."""

    process: subprocess.Popen[Any]
    batch_path: Path
    generated_batch: bool
    keep_batch: bool = False
    stdout: Any = None
    stderr: Any = None

    def poll(self) -> int | None:
        return self.process.poll()

    def wait(self, timeout: float | None = None, *, check: bool = False) -> int:
        """Wait for IDL and remove a successful generated batch when requested."""
        self.stdout, self.stderr = self.process.communicate(timeout=timeout)
        return_code = self.process.returncode
        self._cleanup(return_code)
        if check and return_code:
            raise subprocess.CalledProcessError(return_code, self.process.args)
        return return_code

    def terminate(self) -> None:
        self.process.terminate()

    def kill(self) -> None:
        self.process.kill()

    def communicate(
        self, input: str | bytes | None = None, timeout: float | None = None,
        *, check: bool = False,
    ) -> tuple[Any, Any]:
        """Exchange data with IDL, wait for it, and return stdout and stderr."""
        self.stdout, self.stderr = self.process.communicate(input=input, timeout=timeout)
        return_code = self.process.returncode
        self._cleanup(return_code)
        if check and return_code:
            raise subprocess.CalledProcessError(
                return_code, self.process.args, self.stdout, self.stderr)
        return self.stdout, self.stderr

    def _cleanup(self, return_code: int) -> None:
        if self.generated_batch and not self.keep_batch and return_code == 0:
            self.batch_path.unlink(missing_ok=True)


def _open_redirect(value: Redirect | str, mode: str) -> tuple[Any, IO[Any] | None]:
    if value == "stdout":
        return subprocess.STDOUT, None
    if isinstance(value, (str, os.PathLike)):
        path = Path(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open(mode)
        return stream, stream
    return value, None


def _make_batch(source: str, cwd: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".bm", prefix="thmsoc_",
        dir=cwd, delete=False,
    ) as stream:
        stream.write(source)
        return Path(stream.name)


def run_idl(
    batch_path: Pathish | None = None,
    *,
    source: str | None = None,
    cwd: Pathish | None = None,
    stdout: Redirect = None,
    stderr: Redirect | str = None,
    stdout_path: Pathish | None = None,
    stderr_path: Pathish | None = None,
    append: bool = False,
    stdin: Redirect = None,
    stdin_path: Pathish | None = None,
    args: Sequence[str] = (),
    executable: Pathish | None = None,
    startup: Pathish | None = None,
    environment: Mapping[str, str] | None = None,
    config_path: Pathish | None = None,
    wait: bool = True,
    timeout: float | None = None,
    check: bool = False,
    keep_batch: bool = False,
) -> subprocess.CompletedProcess[Any] | IdlJob:
    """Run an IDL batch file synchronously or asynchronously.

    Supply exactly one of ``batch_path`` and ``source``. ``stderr="stdout"``
    combines the logs. Generated batches are removed after success unless
    ``keep_batch`` is true, and retained after failure for diagnosis.
    """
    if (batch_path is None) == (source is None):
        raise ValueError("supply exactly one of batch_path and source")
    if stdout is not None and stdout_path is not None:
        raise ValueError("supply only one of stdout and stdout_path")
    if stderr is not None and stderr_path is not None:
        raise ValueError("supply only one of stderr and stderr_path")
    if stdin is not None and stdin_path is not None:
        raise ValueError("supply only one of stdin and stdin_path")

    working_dir = (Path(cwd) if cwd is not None else Path.cwd()).resolve()
    working_dir.mkdir(parents=True, exist_ok=True)
    if not working_dir.is_dir():
        raise NotADirectoryError(working_dir)

    settings = load_idl_config(config_path)
    child_env = os.environ.copy()
    child_env.update(settings.environment)
    if settings.path:
        child_env["IDL_PATH"] = os.pathsep.join(settings.path)
    selected_startup = Path(startup) if startup is not None else settings.startup
    if selected_startup is not None:
        child_env["IDL_STARTUP"] = str(selected_startup)
    if environment:
        if not all(isinstance(key, str) and isinstance(value, str)
                   for key, value in environment.items()):
            raise ValueError("environment keys and values must be strings")
        child_env.update(environment)

    selected_executable = (
        os.fspath(executable) if executable is not None else settings.executable
    )
    generated = source is not None
    actual_batch = (_make_batch(source, working_dir) if source is not None
                    else Path(batch_path))
    if not actual_batch.is_absolute():
        actual_batch = working_dir / actual_batch
    if not actual_batch.is_file():
        raise FileNotFoundError(actual_batch)
    command = [selected_executable, *args, str(actual_batch)]
    output_mode = "ab" if append else "wb"
    opened: list[IO[Any]] = []
    try:
        stdout_value, stdout_stream = _open_redirect(
            stdout_path if stdout_path is not None else stdout, output_mode)
        stderr_value, stderr_stream = _open_redirect(
            stderr_path if stderr_path is not None else stderr, output_mode)
        stdin_value, stdin_stream = _open_redirect(
            stdin_path if stdin_path is not None else stdin, "rb")
        opened.extend(stream for stream in (stdout_stream, stderr_stream, stdin_stream)
                      if stream is not None)
        process = subprocess.Popen(
            command, cwd=working_dir, env=child_env, stdin=stdin_value,
            stdout=stdout_value, stderr=stderr_value,
        )
    except Exception:
        if generated and not keep_batch:
            actual_batch.unlink(missing_ok=True)
        raise
    finally:
        for stream in opened:
            stream.close()

    job = IdlJob(process, actual_batch, generated, keep_batch)
    if not wait:
        return job
    try:
        captured_stdout, captured_stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    return_code = process.returncode
    job._cleanup(return_code)
    completed = subprocess.CompletedProcess(
        command, return_code, captured_stdout, captured_stderr)
    if check:
        completed.check_returncode()
    return completed
