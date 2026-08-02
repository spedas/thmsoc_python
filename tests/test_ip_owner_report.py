import io
import ipaddress
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from thmsoc.ip_owner_report import (
    bootstrap_services,
    covering_entry,
    rdap_owner,
    read_addresses,
    write_report,
)


class IpOwnerReportTests(unittest.TestCase):
    def test_input_counts_duplicates_and_ignores_blanks(self):
        result = read_addresses(io.StringIO("192.0.2.1\n192.0.2.1\n\n198.51.100.2\n"))
        self.assertEqual(result[ipaddress.IPv4Address("192.0.2.1")], 2)
        self.assertEqual(len(result), 2)

    def test_input_reports_bad_line(self):
        with self.assertRaisesRegex(ValueError, "line 2"):
            read_addresses(io.StringIO("192.0.2.1\nnot-an-ip\n"))

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
        counts = read_addresses(io.StringIO("192.0.2.1\n192.0.2.1\n198.51.100.1\n"))
        output = io.StringIO()
        with TemporaryDirectory() as directory:
            write_report(counts, output, Path(directory) / "cache.json")
        rows = output.getvalue().splitlines()
        self.assertTrue(rows[1].startswith("2\t1\tSmall ISP\tAS64501"))
        self.assertTrue(rows[2].startswith("1\t1\tLarge ISP\tAS64500"))


if __name__ == "__main__":
    unittest.main()
