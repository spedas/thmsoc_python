"""Summarize requests from an Apache access log."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
import re
from typing import TextIO

MONTHS = {name: i for i, name in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1
)}


# In combined logs the referrer and user agent follow the response size.
# Apache can escape quotes and backslashes inside either field.
COMBINED_TAIL = re.compile(
    r'^\S+\s+"(?P<referer>(?:\\.|[^"\\])*)"\s+"(?P<agent>(?:\\.|[^"\\])*)"(?:\s|$)'
)


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


@dataclass
class TrafficCounts:
    """Totals for every input line and counts for requested output types."""

    requests: int = 0
    matches: int = 0
    response_bytes: int = 0
    ips: Counter[str] = field(default_factory=Counter)
    user_agents: Counter[str] = field(default_factory=Counter)
    urls: Counter[str] = field(default_factory=Counter)
    referers: Counter[str] = field(default_factory=Counter)


def count_requests(
    lines: Iterable[str], status: str, *,
    time_range: tuple[float, float] | None = None,
    ip_filters: tuple[str, ...] = (),
    url_filters: RegexFilters = RegexFilters(),
    user_agent_filters: RegexFilters = RegexFilters(),
    referer_filters: RegexFilters = RegexFilters(),
    save_matches: TextIO | None = None,
    collect_ips: bool = False,
    collect_user_agents: bool = False,
    collect_referers: bool = False,
    collect_urls: bool = False,
) -> TrafficCounts:
    """Count all input lines; stream matches and aggregate requested fields."""
    counts = TrafficCounts()
    for line in lines:
        counts.requests += 1
        fields = line.split(maxsplit=9)
        if len(fields) < 10 or not fields[3].startswith("["):
            continue
        if not fields[8].isascii() or not fields[8].isdigit() or len(fields[8]) != 3:
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
        agent = referer = None
        if (
            collect_user_agents or collect_referers
            or user_agent_filters.include or user_agent_filters.exclude
            or referer_filters.include or referer_filters.exclude
        ):
            tail = COMBINED_TAIL.match(fields[9])
            if tail:
                agent = tail["agent"] if tail["agent"] != "-" else None
                referer = tail["referer"] if tail["referer"] != "-" else None
            if not (user_agent_filters.matches(agent) and referer_filters.matches(referer)):
                continue
        counts.matches += 1
        try:
            response_bytes = int(fields[9].split(maxsplit=1)[0])
        except ValueError:
            response_bytes = 0  # Apache uses "-" when no bytes were sent.
        counts.response_bytes += max(0, response_bytes)
        if save_matches is not None:
            save_matches.write(line)
        if collect_ips:
            counts.ips[address] += 1
        if collect_urls:
            counts.urls[url] += 1
        if collect_user_agents:
            counts.user_agents[agent if agent is not None else "-"] += 1
        if collect_referers:
            counts.referers[referer if referer is not None else "-"] += 1
    return counts


def write_report(
    lines: Iterable[str], output: TextIO, status: str, *,
    time_range: tuple[float, float] | None = None,
    ip_filters: tuple[str, ...] = (),
    url_filters: RegexFilters = RegexFilters(),
    user_agent_filters: RegexFilters = RegexFilters(),
    referer_filters: RegexFilters = RegexFilters(),
    save_matches: TextIO | None = None,
    save_ips: TextIO | None = None,
    save_user_agents: TextIO | None = None,
    save_urls: TextIO | None = None,
    save_referer: TextIO | None = None,
) -> None:
    """Print totals, save requested data, and preview each ranked output."""
    counts = count_requests(
        lines, status, time_range=time_range, ip_filters=ip_filters,
        url_filters=url_filters, user_agent_filters=user_agent_filters,
        referer_filters=referer_filters,
        save_matches=save_matches, collect_ips=save_ips is not None,
        collect_user_agents=save_user_agents is not None,
        collect_urls=save_urls is not None,
        collect_referers=save_referer is not None,
    )
    print(f"Requests: {counts.requests}", file=output)
    print(f"Matches: {counts.matches}", file=output)
    print(f"Non-matches: {counts.requests - counts.matches}", file=output)
    print(f"Total volume: {counts.response_bytes / 1_000_000:.1f} MB", file=output)
    for label, values, destination in (
        ("IPS", counts.ips, save_ips),
        ("USER AGENTS", counts.user_agents, save_user_agents),
        ("URLS", counts.urls, save_urls),
        ("REFERERS", counts.referers, save_referer),
    ):
        if destination is None:
            continue
        ranked = sorted(values.items(), key=lambda item: (item[1], item[0]), reverse=True)
        print(f"TOP {label}", file=output)
        for index, (value, count) in enumerate(ranked):
            print(count, value, file=destination)
            if index < 25:
                print(count, value, file=output)
        print(f"UNIQUE {label}", len(values), sep="\n", file=output)
