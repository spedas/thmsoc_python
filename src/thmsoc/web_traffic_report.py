"""Summarize requests from an Apache access log."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
import re
from typing import TextIO

MONTHS = {name: i for i, name in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1
)}


# In combined logs the referrer and user agent follow the response size.
# Apache can escape quotes and backslashes inside either field.
COMBINED_TAIL = re.compile(r'^\S+\s+"(?:\\.|[^"\\])*"\s+"((?:\\.|[^"\\])*)"(?:\s|$)')


@dataclass(frozen=True)
class RegexFilters:
    """Require all inclusions to match and all exclusions to miss."""

    include: tuple[re.Pattern[str], ...] = ()
    exclude: tuple[re.Pattern[str], ...] = ()

    def matches(self, value: str | None) -> bool:
        if value is None:
            return not self.include
        return all(pattern.search(value) for pattern in self.include) and not any(
            pattern.search(value) for pattern in self.exclude
        )


def parse_log_time(clock: str, offset: str) -> float:
    """Return the instant recorded by an Apache timestamp and UTC offset."""
    day, month, rest = clock[1:].split("/")
    date, hour, minute, second = rest.split(":")
    if not offset.endswith("]"):
        raise ValueError("missing timestamp terminator")
    zone = offset[:-1]
    if len(zone) != 5 or zone[0] not in "+-" or not zone[1:].isdigit():
        raise ValueError("invalid UTC offset")
    hours, minutes = int(zone[1:3]), int(zone[3:5])
    if hours > 23 or minutes > 59:
        raise ValueError("invalid UTC offset")
    delta = timedelta(hours=hours, minutes=minutes)
    tz = timezone(-delta if zone[0] == "-" else delta)
    return datetime(int(date), MONTHS[month], int(day), int(hour), int(minute),
                    int(second), tzinfo=tz).timestamp()


def matches_ip(address: str, pattern: str) -> bool:
    """Match a literal substring or a shell glob against a source address."""
    if any(char in pattern for char in "*?["):
        return fnmatchcase(address, pattern)
    return pattern in address


def count_requests(
    lines: Iterable[str], status: str, *,
    time_range: tuple[float, float] | None = None,
    ip_filters: tuple[str, ...] = (),
    url_filters: RegexFilters = RegexFilters(),
    user_agent_filters: RegexFilters = RegexFilters(),
) -> tuple[Counter[str], Counter[str]]:
    """Count source IPs and request targets, optionally within [start, end)."""
    ips: Counter[str] = Counter()
    urls: Counter[str] = Counter()
    for line in lines:
        fields = line.split(maxsplit=9)
        if len(fields) < 9 or not fields[3].startswith("["):
            continue
        address = fields[0]
        if not all(matches_ip(address, pattern) for pattern in ip_filters):
            continue
        code = fields[8]
        if status == "successful" and code != "200":
            continue
        if status == "unsuccessful" and not (
            len(code) == 3 and code[0] in "45" and code[1:].isascii() and code[1:].isdigit()
        ):
            continue
        if time_range is not None:
            try:
                timestamp = parse_log_time(fields[3], fields[4])
            except (KeyError, ValueError, OverflowError):
                continue
            if not time_range[0] <= timestamp < time_range[1]:
                continue
        url = fields[6]
        if not url_filters.matches(url):
            continue
        if user_agent_filters.include or user_agent_filters.exclude:
            tail = COMBINED_TAIL.match(fields[9]) if len(fields) > 9 else None
            agent = tail[1] if tail and tail[1] != "-" else None
            if not user_agent_filters.matches(agent):
                continue
        ips[address] += 1
        urls[url] += 1
    return ips, urls


def write_report(
    lines: Iterable[str], output: TextIO, status: str, *,
    time_range: tuple[float, float] | None = None,
    ip_filters: tuple[str, ...] = (),
    url_filters: RegexFilters = RegexFilters(),
    user_agent_filters: RegexFilters = RegexFilters(),
) -> None:
    """Print the top 30 IPs and URLs and the total number of unique IPs."""
    ips, urls = count_requests(
        lines, status, time_range=time_range, ip_filters=ip_filters,
        url_filters=url_filters, user_agent_filters=user_agent_filters,
    )
    if time_range is None:
        print("TIME RANGE: entire file", file=output)
    else:
        start, end = (
            datetime.fromtimestamp(bound, timezone.utc).isoformat().replace("+00:00", "Z")
            for bound in time_range
        )
        print(f"TIME RANGE: [{start}, {end})", file=output)
    for title, counts in (("TOP IPS", ips), ("TOP URLS", urls)):
        print(title, file=output)
        ranked = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
        for value, count in ranked[:30]:
            print(count, value, file=output)
    print("UNIQUE IPS", len(ips), sep="\n", file=output)
