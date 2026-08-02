"""Resolve IPv4 traffic sources to registered owners and origin ASNs."""

from __future__ import annotations

import ipaddress
import json
import os
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, TextIO

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


def get_json(url: str, timeout: float, context: ssl.SSLContext) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/rdap+json, application/json", "User-Agent": USER_AGENT},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return json.load(response)
        except (OSError, json.JSONDecodeError) as exc:
            retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code == 429 or exc.code >= 500
            if attempt == 2 or not retryable:
                raise LookupError(f"lookup failed for {url}: {exc}") from exc
            delay = 2.0**attempt
            if isinstance(exc, urllib.error.HTTPError) and exc.headers:
                try:
                    delay = min(30.0, float(exc.headers.get("Retry-After", delay)))
                except ValueError:
                    pass
            time.sleep(delay)
    raise AssertionError("unreachable")


def read_addresses(lines: Iterable[str]) -> Counter[ipaddress.IPv4Address]:
    """Read, validate, and count IPv4 addresses, ignoring blank lines."""
    counts: Counter[ipaddress.IPv4Address] = Counter()
    for line_number, line in enumerate(lines, 1):
        value = line.strip()
        if not value:
            continue
        try:
            counts[ipaddress.IPv4Address(value)] += 1
        except ipaddress.AddressValueError as exc:
            raise ValueError(f"line {line_number}: invalid IPv4 address: {value!r}") from exc
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


def rdap_lookup(address: ipaddress.IPv4Address, cache: dict[str, Any], timeout: float,
                context: ssl.SSLContext) -> dict[str, Any]:
    if cached := covering_entry(cache["rdap"], address):
        return cached
    if cache["bootstrap"] is None:
        cache["bootstrap"] = get_json(IANA_BOOTSTRAP, timeout, context)
    endpoint = next((url for network, url in bootstrap_services(cache["bootstrap"])
                     if address in network), None)
    if endpoint is None:
        raise LookupError(f"no authoritative RDAP service found for {address}")
    data = get_json(f"{endpoint}/ip/{address}", timeout, context)
    try:
        start = ipaddress.IPv4Address(data["startAddress"])
        end = ipaddress.IPv4Address(data["endAddress"])
    except (KeyError, ipaddress.AddressValueError) as exc:
        raise LookupError(f"RDAP returned no usable IPv4 range for {address}") from exc
    entry = {"start": int(start), "end": int(end), "range": f"{start}-{end}",
             "owner": rdap_owner(data)}
    cache["rdap"].append(entry)
    return entry


def routing_lookup(address: ipaddress.IPv4Address, cache: dict[str, Any], timeout: float,
                   context: ssl.SSLContext) -> dict[str, Any]:
    if cached := covering_entry(cache["routing"], address):
        return cached
    query = urllib.parse.urlencode({"resource": str(address)})
    data = get_json(f"{RIPESTAT_NETWORK_INFO}?{query}", timeout, context).get("data", {})
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
                 strict_lookups: bool = False, ca_bundle: Path | None = None) -> None:
    """Look up addresses and write a request-count-sorted TSV report."""
    cache = load_cache(cache_path, refresh)
    context = make_tls_context(ca_bundle)
    groups: dict[tuple[str, tuple[int, ...]], dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "unique": 0, "ranges": set(), "prefixes": set()}
    )
    try:
        total = len(address_counts)
        for position, (address, count) in enumerate(address_counts.items(), 1):
            try:
                registration = rdap_lookup(address, cache, timeout, context)
            except LookupError as exc:
                if strict_lookups:
                    raise
                print(f"warning: {address}: registration lookup: {exc}", file=sys.stderr)
                registration = {"owner": "UNKNOWN", "range": str(address)}
            try:
                routing = routing_lookup(address, cache, timeout, context)
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
