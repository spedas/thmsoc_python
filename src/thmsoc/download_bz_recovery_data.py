from __future__ import annotations

import base64
import getpass
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


DEFAULT_SHARE_URL = "https://cloud.tu-braunschweig.de/s/k93M36pRnXKeQYX"
DEFAULT_DATAROOT = Path("/disks/themisdata")
PROBE_RE = re.compile(r"th[a-e]\Z", re.IGNORECASE)


@dataclass(frozen=True)
class RemoteFile:
    name: str
    url: str
    size: int | None = None


def parse_share_url(share_url: str) -> tuple[str, str]:
    """Return the WebDAV root and share token for a Nextcloud share URL."""
    parsed = urllib.parse.urlsplit(share_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid share URL: {share_url!r}")

    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    try:
        share_index = parts.index("s")
        token = parts[share_index + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("share URL must contain /s/SHARE_TOKEN") from exc

    root = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, "/public.php/webdav/", "", "")
    )
    return root, token


def _authorization(token: str, password: str) -> str:
    encoded = base64.b64encode(f"{token}:{password}".encode()).decode("ascii")
    return f"Basic {encoded}"


def _request(
    url: str,
    token: str,
    password: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
):
    request_headers = {
        "Authorization": _authorization(token, password),
        "User-Agent": "thmsoc-python/download_bz_recovery_data",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, method=method, headers=request_headers)
    return urllib.request.urlopen(request)


def list_remote_files(
    webdav_root: str, token: str, password: str, probe: str, year: int
) -> list[RemoteFile]:
    remote_directory = f"{probe.upper()}/{year}/"
    directory_url = urllib.parse.urljoin(webdav_root, remote_directory)
    with _request(
        directory_url,
        token,
        password,
        method="PROPFIND",
        headers={"Depth": "1"},
    ) as response:
        document = ET.parse(response)

    files: list[RemoteFile] = []
    for item in document.findall("{DAV:}response"):
        href_node = item.find("{DAV:}href")
        resource_type = item.find(".//{DAV:}resourcetype")
        if href_node is None or not href_node.text:
            continue
        if resource_type is not None and resource_type.find("{DAV:}collection") is not None:
            continue

        name = Path(urllib.parse.unquote(urllib.parse.urlsplit(href_node.text).path)).name
        if not name.lower().endswith(".sav") or not name.lower().startswith(f"{probe}_"):
            continue
        size_node = item.find(".//{DAV:}getcontentlength")
        size = int(size_node.text) if size_node is not None and size_node.text else None
        files.append(RemoteFile(name, urllib.parse.urljoin(directory_url, urllib.parse.quote(name)), size))

    return sorted(files, key=lambda remote_file: remote_file.name)


def production_name(remote_name: str, probe: str) -> str:
    """Remove the redundant probe prefix used by the recovery-data share."""
    prefix = f"{probe.lower()}_"
    if remote_name.lower().startswith(prefix):
        return remote_name[len(prefix) :]
    return remote_name


def default_dataroot() -> Path:
    repository_root = Path(__file__).resolve().parents[2]
    config_path = repository_root / "thmsoc_python_config.toml"
    try:
        with config_path.open("rb") as config_file:
            paths = tomllib.load(config_file).get("paths", {})
    except FileNotFoundError:
        return DEFAULT_DATAROOT
    return Path(paths.get("output_dataroot", paths.get("input_dataroot", DEFAULT_DATAROOT)))


def destination_directory(dataroot: Path, probe: str, year: int) -> Path:
    return dataroot / probe.lower() / "l1b" / "fgm" / "sav_files" / str(year)


def download_files(
    files: list[RemoteFile],
    token: str,
    password: str,
    destination: Path,
    probe: str,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for index, remote_file in enumerate(files, start=1):
        target = destination / production_name(remote_file.name, probe)
        partial = target.with_name(f".{target.name}.part")
        size_text = f" ({remote_file.size:,} bytes)" if remote_file.size is not None else ""
        print(f"[{index}/{len(files)}] {remote_file.name}{size_text} -> {target}")
        try:
            with _request(remote_file.url, token, password) as response, partial.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if remote_file.size is not None and partial.stat().st_size != remote_file.size:
                raise OSError(
                    f"incomplete download for {remote_file.name}: "
                    f"expected {remote_file.size} bytes, received {partial.stat().st_size}"
                )
            os.replace(partial, target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        downloaded.append(target)
    return downloaded


def fetch_year(
    probe: str,
    year: int,
    *,
    share_url: str = DEFAULT_SHARE_URL,
    dataroot: Path | None = None,
    password: str = "",
    prompt_for_password: bool = True,
) -> list[Path]:
    probe = probe.lower()
    if not PROBE_RE.fullmatch(probe):
        raise ValueError("probe must be one of tha, thb, thc, thd, or the")
    if year < 2007 or year > 9999:
        raise ValueError("year must be 2007 or later")

    webdav_root, token = parse_share_url(share_url)
    try:
        files = list_remote_files(webdav_root, token, password, probe, year)
    except urllib.error.HTTPError as exc:
        if exc.code != 401 or password or not prompt_for_password:
            raise
        password = getpass.getpass("Share password: ")
        files = list_remote_files(webdav_root, token, password, probe, year)

    if not files:
        raise FileNotFoundError(f"no {probe} .sav files found in the share for {year}")
    destination = destination_directory(dataroot or default_dataroot(), probe, year)
    return download_files(files, token, password, destination, probe)
