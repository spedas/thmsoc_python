import io
import ipaddress
import ssl
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from thmsoc.cli.ip_owner_report import main
from thmsoc.ip_owner_report import (
    HttpClient,
    bootstrap_services,
    covering_entry,
    rdap_owner,
    read_addresses,
    write_report,
)


class IpOwnerReportTests(unittest.TestCase):
    @patch("thmsoc.cli.ip_owner_report.write_report")
    def test_cli_reads_input_file(self, write_report):
        with TemporaryDirectory() as directory:
            input_path = Path(directory) / "addresses.txt"
            input_path.write_text("9 192.0.2.1\n198.51.100.2\n", encoding="utf-8")
            with patch("sys.argv", ["ip_owner_report", "--input", str(input_path)]):
                self.assertEqual(main(), 0)
        counts = write_report.call_args.args[0]
        self.assertEqual(counts[ipaddress.IPv4Address("192.0.2.1")], 9)
        self.assertEqual(counts[ipaddress.IPv4Address("198.51.100.2")], 1)

    def test_input_counts_duplicates_and_ignores_blanks(self):
        result = read_addresses(io.StringIO("192.0.2.1\n192.0.2.1\n\n198.51.100.2\n"))
        self.assertEqual(result[ipaddress.IPv4Address("192.0.2.1")], 2)
        self.assertEqual(len(result), 2)

    def test_input_reports_bad_line(self):
        with self.assertRaisesRegex(ValueError, "line 2"):
            read_addresses(io.StringIO("192.0.2.1\nnot-an-ip\n"), "error")

    def test_input_accepts_optional_repetition_counts(self):
        result = read_addresses(io.StringIO("12 192.0.2.1\n192.0.2.1\n3 198.51.100.2\n"))
        self.assertEqual(result[ipaddress.IPv4Address("192.0.2.1")], 13)
        self.assertEqual(result[ipaddress.IPv4Address("198.51.100.2")], 3)

    def test_input_rejects_invalid_repetition_counts(self):
        with self.assertRaisesRegex(ValueError, "repetition count must be positive"):
            read_addresses(io.StringIO("0 192.0.2.1\n"))
        with self.assertRaisesRegex(ValueError, "repetition count must be an integer"):
            read_addresses(io.StringIO("many 192.0.2.1\n"))

    def test_hostname_can_be_ignored_or_resolved(self):
        resolver = lambda hostname: {ipaddress.IPv4Address("203.0.113.9")}
        ignored = read_addresses(io.StringIO("5 example.test\n"), "ignore", resolver)
        resolved = read_addresses(io.StringIO("5 example.test\n"), "resolve", resolver)
        self.assertEqual(ignored, {})
        self.assertEqual(resolved[ipaddress.IPv4Address("203.0.113.9")], 5)

    @patch("thmsoc.ip_owner_report.time.sleep")
    @patch("thmsoc.ip_owner_report.urllib.request.urlopen")
    def test_http_429_honors_retry_after(self, urlopen, sleep):
        rate_limit = urllib.error.HTTPError(
            "https://rdap.example/ip/192.0.2.1", 429, "rate limited",
            {"Retry-After": "7"}, None,
        )
        urlopen.side_effect = [rate_limit, io.BytesIO(b'{"status": "ok"}')]
        client = HttpClient(15.0, ssl.create_default_context(), retries=1,
                            request_delay=0.0)
        self.assertEqual(client.get_json("https://rdap.example/ip/192.0.2.1"),
                         {"status": "ok"})
        self.assertEqual(sleep.call_count, 1)
        self.assertGreaterEqual(sleep.call_args.args[0], 6.9)

    def test_rdap_owner_prefers_registrant(self):
        entity = {
            "roles": ["registrant"],
            "vcardArray": ["vcard", [["fn", {}, "text", "Example ISP"]]],
        }
        self.assertEqual(rdap_owner({"name": "NET-X", "entities": [entity]}), "Example ISP")

    def test_covering_entry_prefers_most_specific_range(self):
        entries = [
            {"start": 0, "end": 1000, "owner": "large"},
            {"start": 100, "end": 200, "owner": "small"},
        ]
        result = covering_entry(entries, ipaddress.IPv4Address(150))
        self.assertEqual(result["owner"], "small")

    def test_bootstrap_parsing(self):
        data = {"services": [[["192.0.2.0/24"], ["https://rdap.example/"]]]}
        self.assertEqual(bootstrap_services(data)[0][1], "https://rdap.example")

    @patch("thmsoc.ip_owner_report.routing_lookup")
    @patch("thmsoc.ip_owner_report.rdap_lookup")
    def test_report_groups_and_sorts(self, rdap_lookup, routing_lookup):
        rdap_lookup.side_effect = [
            {"owner": "Small ISP", "range": "198.51.100.0-198.51.100.255"},
            {"owner": "Large ISP", "range": "192.0.2.0-192.0.2.255"},
        ]
        routing_lookup.side_effect = [
            {"asns": [64501], "prefix": "198.51.100.0/24"},
            {"asns": [64500], "prefix": "192.0.2.0/24"},
        ]
        counts = read_addresses(io.StringIO("12 192.0.2.1\n198.51.100.1\n"))
        output = io.StringIO()
        with TemporaryDirectory() as directory:
            write_report(counts, output, Path(directory) / "cache.json")
        rows = output.getvalue().splitlines()
        self.assertTrue(rows[1].startswith("12\t1\tSmall ISP\tAS64501"))
        self.assertTrue(rows[2].startswith("1\t1\tLarge ISP\tAS64500"))


if __name__ == "__main__":
    unittest.main()
