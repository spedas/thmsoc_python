"""Aggregate weighted IP address and hostname traffic by rDNS base domain."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO

NO_RDNS = "no_rDNS"


def read_sources(lines: Iterable[str]) -> Counter[str]:
    """Read ``SOURCE`` or ``COUNT SOURCE`` lines and return weighted counts."""
    counts: Counter[str] = Counter()
    for line_number, line in enumerate(lines, 1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) == 1:
            count, source = 1, fields[0]
        elif len(fields) == 2:
            try:
                count = int(fields[0])
            except ValueError as exc:
                raise ValueError(
                    f"line {line_number}: repetition count must be an integer"
                ) from exc
            if count <= 0:
                raise ValueError(f"line {line_number}: repetition count must be positive")
            source = fields[1]
        else:
            raise ValueError(f"line {line_number}: expected SOURCE or COUNT SOURCE")

        try:
            normalized = str(ipaddress.IPv4Address(source))
        except ipaddress.AddressValueError:
            normalized = source.rstrip(".").lower()
        counts[normalized] += count
    return counts


def second_level_domain(hostname: str) -> str:
    """Return the final two labels of a hostname, or ``no_rDNS``."""
    labels = [label for label in hostname.rstrip(".").lower().split(".") if label]
    return ".".join(labels[-2:]) if len(labels) >= 2 else NO_RDNS


def top_level_domain(hostname: str) -> str:
    """Return the final label of a hostname, or ``no_rDNS``."""
    labels = [label for label in hostname.rstrip(".").lower().split(".") if label]
    return labels[-1] if len(labels) >= 2 else NO_RDNS


def aggregate_domain(hostname: str, domain_level: str) -> str:
    if domain_level == "top":
        return top_level_domain(hostname)
    if domain_level == "second":
        return second_level_domain(hostname)
    raise ValueError(f"unsupported domain level: {domain_level!r}")


def system_reverse_resolver(address: ipaddress.IPv4Address) -> str:
    return socket.gethostbyaddr(str(address))[0]


def empty_cache() -> dict[str, Any]:
    return {"version": 1, "addresses": {}}


def load_cache(path: Path, refresh: bool = False) -> dict[str, Any]:
    if refresh or not path.exists():
        return empty_cache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if data.get("version") == 1 else empty_cache()
    except (OSError, json.JSONDecodeError):
        print(f"warning: ignoring unreadable cache {path}", file=sys.stderr)
        return empty_cache()


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    """Atomically save rDNS results, including negative lookups."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(cache, output, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def reverse_name(
    address: ipaddress.IPv4Address,
    cache: dict[str, Any],
    resolver: Callable[[ipaddress.IPv4Address], str],
) -> str | None:
    key = str(address)
    cached = cache["addresses"].get(key, ...)
    if cached is not ...:
        return cached
    try:
        hostname = resolver(address).rstrip(".").lower()
    except (OSError, UnicodeError):
        hostname = None
    cache["addresses"][key] = hostname
    return hostname


def write_report(
    source_counts: Counter[str],
    output: TextIO,
    cache_path: Path,
    *,
    refresh: bool = False,
    domain_level: str = "second",
    resolver: Callable[[ipaddress.IPv4Address], str] = system_reverse_resolver,
) -> None:
    """Resolve IPv4 sources and write a request-count-sorted TSV report."""
    cache = load_cache(cache_path, refresh)
    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "sources": set(), "hostnames": set()}
    )
    try:
        for position, (source, count) in enumerate(source_counts.items(), 1):
            try:
                address = ipaddress.IPv4Address(source)
            except ipaddress.AddressValueError:
                hostname = source
            else:
                hostname = reverse_name(address, cache, resolver)
            domain = aggregate_domain(hostname, domain_level) if hostname else NO_RDNS
            group = groups[domain]
            group["requests"] += count
            group["sources"].add(source)
            if hostname:
                group["hostnames"].add(hostname)
            if position % 100 == 0:
                print(f"processed {position}/{len(source_counts)} unique sources",
                      file=sys.stderr)
                save_cache(cache_path, cache)
    finally:
        save_cache(cache_path, cache)

    print(f"requests\tunique_sources\t{domain_level}_level_domain\thostnames",
          file=output)
    ordered = sorted(groups.items(), key=lambda item: (-item[1]["requests"], item[0]))
    for domain, group in ordered:
        fields = (
            str(group["requests"]),
            str(len(group["sources"])),
            domain,
            ",".join(sorted(group["hostnames"])),
        )
        print("\t".join(fields), file=output)
