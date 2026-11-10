"""Summarize requests from an Apache access log."""

from collections import Counter
from collections.abc import Iterable
from typing import TextIO


def count_requests(
    lines: Iterable[str], minute: str, status: str
) -> tuple[Counter[str], Counter[str]]:
    """Count source IPs and request targets for one Apache log minute."""
    ips: Counter[str] = Counter()
    urls: Counter[str] = Counter()
    prefix = f"[{minute}:"
    for line in lines:
        fields = line.split(maxsplit=9)
        if len(fields) < 9 or not fields[3].startswith(prefix):
            continue
        code = fields[8]
        if status == "successful" and code != "200":
            continue
        if status == "unsuccessful" and not (
            len(code) == 3 and code[0] in "45" and code[1:].isascii() and code[1:].isdigit()
        ):
            continue
        ips[fields[0]] += 1
        urls[fields[6]] += 1
    return ips, urls


def write_report(lines: Iterable[str], output: TextIO, minute: str, status: str) -> None:
    """Print the top 30 IPs and URLs and the total number of unique IPs."""
    ips, urls = count_requests(lines, minute, status)
    print(minute, file=output)
    for title, counts in (("TOP IPS", ips), ("TOP URLS", urls)):
        print(title, file=output)
        ranked = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
        for value, count in ranked[:30]:
            print(count, value, file=output)
    print("UNIQUE IPS", len(ips), sep="\n", file=output)
