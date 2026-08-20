import os
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from thmsoc.idl import IdlJob, load_idl_config, run_idl


FAKE_IDL = """#!/usr/bin/env python3
import os
import pathlib
import sys

batch = pathlib.Path(sys.argv[-1])
print("ARGS=" + "|".join(sys.argv[1:]))
print("CWD=" + os.getcwd())
print("STARTUP=" + os.environ.get("IDL_STARTUP", ""))
print("PATH=" + os.environ.get("IDL_PATH", ""))
print("DEVICE=" + os.environ.get("IDL_DEVICE", ""))
print("SOURCE=" + batch.read_text())
print("STDIN=" + sys.stdin.read())
print("warning", file=sys.stderr)
sys.exit(7 if "FAIL" in batch.read_text() else 0)
"""


class IdlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.executable = self.root / "fake-idl"
        self.executable.write_text(FAKE_IDL, encoding="utf-8")
        self.executable.chmod(self.executable.stat().st_mode | stat.S_IXUSR)
        self.config = self.root / "config.toml"
        self.config.write_text(
            f'''[idl]
executable = "{self.executable}"
startup = "/configured/startup.pro"
path = ["+idl/lib", "thmsoc/idl"]

[environment]
IDL_DEVICE = "Z"
TEST_SETTING = "configured"
''', encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_load_idl_config(self):
        config = load_idl_config(self.config)
        self.assertEqual(config.executable, str(self.executable))
        self.assertEqual(config.path, ("+idl/lib", "thmsoc/idl"))
        self.assertEqual(config.environment["IDL_DEVICE"], "Z")

    def test_generated_batch_environment_arguments_and_combined_log(self):
        work = self.root / "work"
        log = self.root / "logs" / "idl.log"
        result = run_idl(
            source="print, 'hello'\nexit\n", cwd=work, stdout_path=log,
            stderr="stdout", args=["-quiet"], config_path=self.config,
            environment={"IDL_DEVICE": "NULL"}, check=True,
        )
        self.assertEqual(result.returncode, 0)
        output = log.read_text(encoding="utf-8")
        self.assertIn("ARGS=-quiet|", output)
        self.assertIn(f"CWD={work.resolve()}", output)
        self.assertIn("STARTUP=/configured/startup.pro", output)
        self.assertIn(f"PATH=+idl/lib{os.pathsep}thmsoc/idl", output)
        self.assertIn("DEVICE=NULL", output)
        self.assertIn("SOURCE=print, 'hello'", output)
        self.assertIn("warning", output)
        batch = Path(result.args[-1])
        self.assertFalse(batch.exists())

    def test_existing_relative_batch_is_resolved_from_working_directory(self):
        work = self.root / "work"
        work.mkdir()
        batch = work / "job.bm"
        batch.write_text("exit\n", encoding="utf-8")
        result = run_idl(
            "job.bm", cwd=work, stdout=subprocess.PIPE,
            config_path=self.config, check=True,
        )
        self.assertIn(f"SOURCE={batch.read_text()}", result.stdout.decode())
        self.assertTrue(batch.exists())

    def test_failed_generated_batch_is_retained(self):
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            run_idl(source="FAIL\n", cwd=self.root / "failed",
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    config_path=self.config, check=True)
        self.assertEqual(raised.exception.returncode, 7)
        self.assertTrue(Path(raised.exception.cmd[-1]).exists())

    def test_keep_generated_batch_after_success(self):
        result = run_idl(source="exit\n", cwd=self.root / "kept",
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         config_path=self.config, keep_batch=True, check=True)
        self.assertTrue(Path(result.args[-1]).exists())

    def test_asynchronous_job(self):
        job = run_idl(
            source="exit\n", cwd=self.root / "async", stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, config_path=self.config, wait=False,
        )
        self.assertIsInstance(job, IdlJob)
        self.assertEqual(job.wait(check=True), 0)
        self.assertIn(b"SOURCE=exit", job.stdout)
        self.assertFalse(job.batch_path.exists())

    def test_stdin_path_and_appended_log(self):
        stdin_path = self.root / "answers.txt"
        stdin_path.write_text("yes\n", encoding="utf-8")
        log = self.root / "append.log"
        log.write_text("before\n", encoding="utf-8")
        run_idl(
            source="exit\n", cwd=self.root / "stdin", stdin_path=stdin_path,
            stdout_path=log, stderr="stdout", append=True,
            config_path=self.config, check=True,
        )
        output = log.read_text(encoding="utf-8")
        self.assertTrue(output.startswith("before\n"))
        self.assertIn("STDIN=yes", output)

    def test_rejects_ambiguous_inputs_and_redirects(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            run_idl(config_path=self.config)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            run_idl("job.bm", source="exit", config_path=self.config)
        with self.assertRaisesRegex(ValueError, "stdout"):
            run_idl(source="exit", stdout=self.root / "one",
                    stdout_path=self.root / "two", config_path=self.config)


if __name__ == "__main__":
    unittest.main()
