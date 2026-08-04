"""Resolve IPv4 traffic sources to registered owners and origin ASNs."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO

IANA_BOOTSTRAP = "https://data.iana.org/rdap/ipv4.json"
RIPESTAT_NETWORK_INFO = "https://stat.ripe.net/data/network-info/data.json"
USER_AGENT = "thmsoc-ip-owner-report/1.0"


class LookupError(RuntimeError):
    """An external registration or routing lookup failed."""


def make_tls_context(ca_bundle: Path | None = None) -> ssl.SSLContext:
    if ca_bundle is not None:
        return ssl.create_default_context(cafile=ca_bundle)
    if sys.platform == "darwin" and Path("/etc/ssl/cert.pem").exists():
        return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return ssl.create_default_context()


def retry_delay(error: urllib.error.HTTPError, attempt: int) -> float:
    """Return a server-requested delay, or exponential backoff if absent."""
    retry_after = error.headers.get("Retry-After") if error.headers else None
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return min(60.0, 2.0**attempt)


class HttpClient:
    """JSON HTTP client with per-host pacing and rate-limit-aware retries."""

    def __init__(self, timeout: float, context: ssl.SSLContext, retries: int = 8,
                 request_delay: float = 0.25) -> None:
        self.timeout = timeout
        self.context = context
        self.retries = retries
        self.request_delay = request_delay
        self.next_request: dict[str, float] = {}

    def get_json(self, url: str) -> dict[str, Any]:
        host = urllib.parse.urlsplit(url).netloc
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/rdap+json, application/json",
                     "User-Agent": USER_AGENT},
        )
        for attempt in range(self.retries + 1):
            wait = self.next_request.get(host, 0.0) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.next_request[host] = time.monotonic() + self.request_delay
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout, context=self.context
                ) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or exc.code >= 500
                if attempt == self.retries or not retryable:
                    raise LookupError(f"lookup failed for {url}: {exc}") from exc
                delay = retry_delay(exc, attempt)
                self.next_request[host] = max(
                    self.next_request.get(host, 0.0), time.monotonic() + delay
                )
                print(
                    f"warning: {host} returned HTTP {exc.code}; retrying in "
                    f"{delay:.1f} seconds ({attempt + 1}/{self.retries})",
                    file=sys.stderr,
                )
            except (OSError, json.JSONDecodeError) as exc:
                if attempt == self.retries:
                    raise LookupError(f"lookup failed for {url}: {exc}") from exc
                delay = min(60.0, 2.0**attempt)
                self.next_request[host] = max(
                    self.next_request.get(host, 0.0), time.monotonic() + delay
                )
        raise AssertionError("unreachable")


def system_resolver(hostname: str) -> set[ipaddress.IPv4Address]:
    results = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
    return {ipaddress.IPv4Address(result[4][0]) for result in results}


def read_addresses(
    lines: Iterable[str],
    hostname_mode: str = "ignore",
    resolver: Callable[[str], set[ipaddress.IPv4Address]] = system_resolver,
) -> Counter[ipaddress.IPv4Address]:
    """Read ``ADDRESS`` or ``COUNT ADDRESS`` lines and return weighted counts."""
    counts: Counter[ipaddress.IPv4Address] = Counter()
    for line_number, line in enumerate(lines, 1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) == 1:
            count, value = 1, fields[0]
        elif len(fields) == 2:
            try:
                count = int(fields[0])
            except ValueError as exc:
                raise ValueError(
                    f"line {line_number}: repetition count must be an integer"
                ) from exc
            if count <= 0:
                raise ValueError(f"line {line_number}: repetition count must be positive")
            value = fields[1]
        else:
            raise ValueError(f"line {line_number}: expected ADDRESS or COUNT ADDRESS")
        try:
            addresses = {ipaddress.IPv4Address(value)}
        except ipaddress.AddressValueError as exc:
            if hostname_mode == "error":
                raise ValueError(
                    f"line {line_number}: invalid IPv4 address: {value!r}"
                ) from exc
            if hostname_mode == "ignore":
                print(f"warning: line {line_number}: ignoring hostname {value!r}",
                      file=sys.stderr)
                continue
            try:
                addresses = resolver(value)
            except (OSError, UnicodeError) as resolve_error:
                print(
                    f"warning: line {line_number}: could not resolve hostname "
                    f"{value!r}: {resolve_error}",
                    file=sys.stderr,
                )
                continue
            if not addresses:
                print(f"warning: line {line_number}: hostname {value!r} has no IPv4 address",
                      file=sys.stderr)
                continue
        for address in addresses:
            counts[address] += count
    return counts


def entity_name(entity: dict[str, Any]) -> str | None:
    vcard = entity.get("vcardArray")
    if not isinstance(vcard, list) or len(vcard) < 2 or not isinstance(vcard[1], list):
        return None
    names: dict[str, str] = {}
    for field in vcard[1]:
        if isinstance(field, list) and len(field) >= 4 and field[0] in ("fn", "org"):
            value = field[3]
            if isinstance(value, list):
                value = " ".join(str(part) for part in value)
            if value:
                names[field[0]] = str(value)
    return names.get("org") or names.get("fn")


def rdap_owner(data: dict[str, Any]) -> str:
    entities = data.get("entities", [])
    for role in ("registrant", "administrative", "technical"):
        for entity in entities:
            if role in entity.get("roles", []) and (name := entity_name(entity)):
                return name
    for entity in entities:
        if name := entity_name(entity):
            return name
    return str(data.get("name") or data.get("handle") or "UNKNOWN")


def empty_cache() -> dict[str, Any]:
    return {"version": 1, "bootstrap": None, "rdap": [], "routing": []}


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
    """Atomically save lookup results so interrupted runs can resume."""
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


def covering_entry(entries: list[dict[str, Any]], address: ipaddress.IPv4Address) -> dict[str, Any] | None:
    number = int(address)
    matches = [entry for entry in entries if entry["start"] <= number <= entry["end"]]
    return min(matches, key=lambda entry: entry["end"] - entry["start"], default=None)


def bootstrap_services(data: dict[str, Any]) -> list[tuple[ipaddress.IPv4Network, str]]:
    result: list[tuple[ipaddress.IPv4Network, str]] = []
    for prefixes, urls in data.get("services", []):
        if urls:
            for prefix in prefixes:
                network = ipaddress.ip_network(prefix)
                if isinstance(network, ipaddress.IPv4Network):
                    result.append((network, urls[0].rstrip("/")))
    return sorted(result, key=lambda item: item[0].prefixlen, reverse=True)


def rdap_lookup(address: ipaddress.IPv4Address, cache: dict[str, Any],
                client: HttpClient) -> dict[str, Any]:
    if cached := covering_entry(cache["rdap"], address):
        return cached
    if cache["bootstrap"] is None:
        cache["bootstrap"] = client.get_json(IANA_BOOTSTRAP)
    endpoint = next((url for network, url in bootstrap_services(cache["bootstrap"])
                     if address in network), None)
    if endpoint is None:
        raise LookupError(f"no authoritative RDAP service found for {address}")
    data = client.get_json(f"{endpoint}/ip/{address}")
    try:
        start = ipaddress.IPv4Address(data["startAddress"])
        end = ipaddress.IPv4Address(data["endAddress"])
    except (KeyError, ipaddress.AddressValueError) as exc:
        raise LookupError(f"RDAP returned no usable IPv4 range for {address}") from exc
    entry = {"start": int(start), "end": int(end), "range": f"{start}-{end}",
             "owner": rdap_owner(data)}
    cache["rdap"].append(entry)
    return entry


def routing_lookup(address: ipaddress.IPv4Address, cache: dict[str, Any],
                   client: HttpClient) -> dict[str, Any]:
    if cached := covering_entry(cache["routing"], address):
        return cached
    query = urllib.parse.urlencode({"resource": str(address)})
    data = client.get_json(f"{RIPESTAT_NETWORK_INFO}?{query}").get("data", {})
    prefix = data.get("prefix")
    asns = sorted({int(asn) for asn in data.get("asns", [])})
    if prefix:
        network = ipaddress.IPv4Network(prefix)
        start, end = int(network.network_address), int(network.broadcast_address)
    else:
        prefix, start, end = "UNROUTED", int(address), int(address)
    entry = {"start": start, "end": end, "prefix": prefix, "asns": asns}
    cache["routing"].append(entry)
    return entry


def clean_field(value: object) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_report(address_counts: Counter[ipaddress.IPv4Address], output: TextIO, cache_path: Path,
                 *, refresh: bool = False, timeout: float = 15.0,
                 strict_lookups: bool = False, ca_bundle: Path | None = None,
                 retries: int = 8, request_delay: float = 0.25) -> None:
    """Look up addresses and write a request-count-sorted TSV report."""
    cache = load_cache(cache_path, refresh)
    context = make_tls_context(ca_bundle)
    client = HttpClient(timeout, context, retries, request_delay)
    groups: dict[tuple[str, tuple[int, ...]], dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "unique": 0, "ranges": set(), "prefixes": set()}
    )
    try:
        total = len(address_counts)
        for position, (address, count) in enumerate(address_counts.items(), 1):
            try:
                registration = rdap_lookup(address, cache, client)
            except LookupError as exc:
                if strict_lookups:
                    raise
                print(f"warning: {address}: registration lookup: {exc}", file=sys.stderr)
                registration = {"owner": "UNKNOWN", "range": str(address)}
            try:
                routing = routing_lookup(address, cache, client)
            except LookupError as exc:
                if strict_lookups:
                    raise
                print(f"warning: {address}: routing lookup: {exc}", file=sys.stderr)
                routing = {"asns": [], "prefix": "UNKNOWN"}
            key = (registration["owner"], tuple(routing["asns"]))
            group = groups[key]
            group["requests"] += count
            group["unique"] += 1
            group["ranges"].add(registration["range"])
            group["prefixes"].add(routing["prefix"])
            if position % 100 == 0:
                print(f"looked up {position}/{total} unique addresses", file=sys.stderr)
                save_cache(cache_path, cache)
    finally:
        save_cache(cache_path, cache)

    print("requests\tunique_ips\torganization\torigin_asns\tregistered_ranges\trouted_prefixes",
          file=output)
    for (owner, asns), group in sorted(groups.items(),
                                       key=lambda item: (-item[1]["requests"], item[0])):
        fields = (group["requests"], group["unique"], owner,
                  ",".join(f"AS{asn}" for asn in asns) or "UNROUTED/UNKNOWN",
                  ",".join(sorted(group["ranges"])), ",".join(sorted(group["prefixes"])))
        print("\t".join(clean_field(field) for field in fields), file=output)
