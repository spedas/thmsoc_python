import io
import subprocess
from pathlib import Path

from thmsoc.cli import launch_idl_batches as cli
from thmsoc.idl import IdlJob
from thmsoc.launch_idl_batches import launch_idl_batches


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid


def test_launches_nonblank_entries_detached_with_colocated_logs(
    tmp_path, monkeypatch
):
    calls = []

    def fake_run_idl(batch_path, **kwargs):
        calls.append((Path(batch_path), kwargs))
        return IdlJob(FakeProcess(100 + len(calls)), Path(batch_path), False)

    monkeypatch.setattr("thmsoc.launch_idl_batches.run_idl", fake_run_idl)

    jobs = launch_idl_batches(
        ["first.bm\n", "\n", "subdirectory/second.bm\n"], tmp_path
    )

    assert [job.process.pid for job in jobs] == [101, 102]
    assert calls[0][0] == tmp_path / "first.bm"
    assert calls[1][0] == tmp_path / "subdirectory/second.bm"
    assert calls[0][1] == {
        "cwd": tmp_path,
        "stdin": subprocess.DEVNULL,
        "stdout_path": tmp_path / "first.bm.log",
        "stderr": "stdout",
        "config_path": None,
        "wait": False,
        "start_new_session": True,
    }
    assert calls[1][1]["stdout_path"] == tmp_path / "second.bm.log"


def test_cli_file_uses_master_list_directory(tmp_path, monkeypatch, capsys):
    master_list = tmp_path / "master_list.txt"
    master_list.write_text("first.bm\nsecond.bm\n", encoding="utf-8")
    captured = {}

    def fake_launch(lines, directory, **kwargs):
        captured["lines"] = list(lines)
        captured["directory"] = directory
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(cli, "launch_idl_batches", fake_launch)

    assert cli.main([str(master_list), "--config", "custom.toml"]) == 0
    assert captured == {
        "lines": ["first.bm\n", "second.bm\n"],
        "directory": tmp_path,
        "kwargs": {"config_path": "custom.toml"},
    }
    assert capsys.readouterr().out == ""


def test_cli_defaults_to_stdin_and_current_directory(tmp_path, monkeypatch):
    captured = {}

    def fake_launch(lines, directory, **kwargs):
        captured["lines"] = list(lines)
        captured["directory"] = directory
        return []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "launch_idl_batches", fake_launch)

    assert cli.main([], stdin=io.StringIO("batch.bm\n")) == 0
    assert captured == {"lines": ["batch.bm\n"], "directory": tmp_path}
