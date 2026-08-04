import io
import ipaddress
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from thmsoc.cli.ip_rdns_report import main
from thmsoc.ip_rdns_report import (
    NO_RDNS,
    aggregate_domain,
    read_sources,
    second_level_domain,
    top_level_domain,
    write_report,
)


class IpRdnsReportTests(unittest.TestCase):
    def test_input_accepts_mixed_weighted_sources(self):
        result = read_sources(io.StringIO(
            "12 192.12.187.131\n192.12.187.131\n5 Host.BU.EDU.\n"
        ))
        self.assertEqual(result["192.12.187.131"], 13)
        self.assertEqual(result["host.bu.edu"], 5)

    def test_input_rejects_bad_counts_and_extra_fields(self):
        with self.assertRaisesRegex(ValueError, "repetition count must be positive"):
            read_sources(io.StringIO("0 192.0.2.1\n"))
        with self.assertRaisesRegex(ValueError, "repetition count must be an integer"):
            read_sources(io.StringIO("many 192.0.2.1\n"))
        with self.assertRaisesRegex(ValueError, "expected SOURCE or COUNT SOURCE"):
            read_sources(io.StringIO("1 192.0.2.1 extra\n"))

    def test_second_level_domain(self):
        self.assertEqual(second_level_domain("host.department.BU.EDU."), "bu.edu")
        self.assertEqual(second_level_domain("localhost"), NO_RDNS)

    def test_top_level_domain(self):
        self.assertEqual(top_level_domain("host.department.BU.EDU."), "edu")
        self.assertEqual(top_level_domain("localhost"), NO_RDNS)
        self.assertEqual(aggregate_domain("host.bu.edu", "top"), "edu")

    def test_report_can_aggregate_by_top_level_domain(self):
        sources = read_sources(io.StringIO("10 host.bu.edu\n5 download.mit.edu\n2 host.example.com\n"))
        output = io.StringIO()
        with TemporaryDirectory() as directory:
            write_report(sources, output, Path(directory) / "cache.json",
                         domain_level="top")
        rows = output.getvalue().splitlines()
        self.assertEqual(rows[0], "requests\tunique_sources\ttop_level_domain\thostnames")
        self.assertEqual(rows[1], "15\t2\tedu\tdownload.mit.edu,host.bu.edu")
        self.assertEqual(rows[2], "2\t1\tcom\thost.example.com")

    def test_report_aggregates_domains_and_missing_rdns(self):
        names = {
            ipaddress.IPv4Address("192.12.187.131"): "host.bu.edu",
            ipaddress.IPv4Address("192.0.2.1"): OSError("no PTR"),
        }

        def resolver(address):
            result = names[address]
            if isinstance(result, Exception):
                raise result
            return result

        sources = read_sources(io.StringIO(
            "10 192.12.187.131\n5 download.bu.edu\n3 192.0.2.1\n"
        ))
        output = io.StringIO()
        with TemporaryDirectory() as directory:
            write_report(sources, output, Path(directory) / "cache.json",
                         resolver=resolver)
        rows = output.getvalue().splitlines()
        self.assertEqual(rows[1], "15\t2\tbu.edu\tdownload.bu.edu,host.bu.edu")
        self.assertEqual(rows[2], "3\t1\tno_rDNS\t")

    def test_negative_rdns_result_is_cached(self):
        resolver_calls = 0

        def resolver(address):
            nonlocal resolver_calls
            resolver_calls += 1
            raise OSError("no PTR")

        sources = read_sources(io.StringIO("192.0.2.1\n"))
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            write_report(sources, io.StringIO(), cache, resolver=resolver)
            write_report(sources, io.StringIO(), cache, resolver=resolver)
        self.assertEqual(resolver_calls, 1)

    @patch("thmsoc.cli.ip_rdns_report.write_report")
    def test_cli_reads_input_file(self, write_report):
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "sources.txt"
            input_path.write_text("7 host.bu.edu\n192.0.2.1\n", encoding="utf-8")
            with patch("sys.argv", ["ip_rdns_report", "--input", str(input_path)]):
                self.assertEqual(main(), 0)
        sources = write_report.call_args.args[0]
        self.assertEqual(sources["host.bu.edu"], 7)
        self.assertEqual(sources["192.0.2.1"], 1)


if __name__ == "__main__":
    unittest.main()
