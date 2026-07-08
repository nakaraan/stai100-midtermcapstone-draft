"""NREL/NSRDB HTTP client for AGENT P.

Fetches hourly solar irradiance data for a given site/year from the NREL
NSRDB API, then parses and time-filters it into the monthly window the user
actually asked for. Follows the small-function, dict-in/dict-out style used
throughout the Week 2-4 notebooks (see notebook2.py, notebook4.py): each step
is a standalone function, and parsing failures degrade gracefully rather than
raising deep into a pipeline.
"""

from __future__ import annotations

import csv
import io
import json as _json
import os
import subprocess
import tempfile
import time
import zipfile
from typing import Optional
from urllib.parse import urlencode

import requests

from config.settings import get_settings
from utils.telemetry import trace_tool

DEFAULT_ATTRIBUTES = ["ghi", "dni", "dhi", "air_temperature", "wind_speed"]
DEFAULT_INTERVAL_MINUTES = 60
# NREL's on-demand export is an async job: the metadata call can return a
# downloadUrl before the file actually lands in S3, which briefly 403s/404s.
# Short backoff covers that race without masking a genuinely bad URL.
DOWNLOAD_RETRY_DELAYS_SECONDS = (2, 4, 8)


class _CurlResponse:
    """Minimal requests.Response-alike backing _curl_get()."""

    def __init__(self, status_code: int, headers: dict, content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            exc = requests.exceptions.HTTPError(f"{self.status_code} error for url")
            exc.response = self
            raise exc


def _curl_get(url: str, params: Optional[dict] = None, timeout: int = 60) -> _CurlResponse:
    """GET via the curl.exe binary instead of the `requests` library.

    Workaround for a machine-specific issue where Python's own requests/socket
    stack hangs indefinitely on outbound HTTPS calls to NREL (DNS, hosts-file
    override, raw socket connects, and NO_PROXY were all tried and ruled out
    as the cause), while curl.exe reliably connects and responds in well under
    a second on the same network. Shelling out to the known-working binary was
    the fastest reliable fix available before a deadline.
    """
    full_url = f"{url}?{urlencode(params)}" if params else url
    body_fd, body_path = tempfile.mkstemp()
    header_fd, header_path = tempfile.mkstemp()
    os.close(body_fd)
    os.close(header_fd)
    try:
        result = subprocess.run(
            ["curl.exe", "-sS", "--max-time", str(timeout), "-D", header_path, "-o", body_path, "-w", "%{http_code}", full_url],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise requests.exceptions.ConnectionError(f"curl.exe failed (exit {result.returncode}): {result.stderr}")
        status_code = int(result.stdout.strip() or 0)
        with open(header_path, "r", encoding="utf-8", errors="ignore") as hf:
            header_lines = hf.read().splitlines()
        with open(body_path, "rb") as bf:
            content = bf.read()
    finally:
        os.unlink(body_path)
        os.unlink(header_path)

    headers = {}
    for line in header_lines:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip()] = value.strip()

    return _CurlResponse(status_code, headers, content)


def _wkt_point(latitude: float, longitude: float) -> str:
    """NREL expects site location as Well-Known Text: POINT(longitude latitude)."""
    return f"POINT({longitude} {latitude})"


def _build_query_params(
    latitude: float,
    longitude: float,
    year: int,
    attributes: Optional[list[str]] = None,
    interval: int = DEFAULT_INTERVAL_MINUTES,
    leap_day: bool = False,
    utc: bool = False,
) -> dict:
    settings = get_settings()
    return {
        "api_key": settings.nrel_api_key,
        "email": settings.nrel_api_email,
        "wkt": _wkt_point(latitude, longitude),
        "names": str(year),
        "attributes": ",".join(attributes or DEFAULT_ATTRIBUTES),
        "interval": interval,
        "leap_day": str(leap_day).lower(),
        "utc": str(utc).lower(),
    }


# ── HTTP GET calls — traced as TOOL spans ───────────────────────────────────

@trace_tool(name="nrel_nsrdb_request")
def fetch_nsrdb_data(
    latitude: float,
    longitude: float,
    year: int,
    attributes: Optional[list[str]] = None,
    interval: int = DEFAULT_INTERVAL_MINUTES,
    leap_day: bool = False,
    utc: bool = False,
) -> requests.Response:
    """GET hourly solar data for one site/year from the configured NSRDB endpoint.

    Depending on the endpoint suffix, NREL returns either the CSV body directly
    (`*-download.csv`) or a JSON payload with an `outputs.downloadUrl` pointing
    to the CSV (`*-download.json`, used for larger on-demand requests). Both
    cases are handled by `get_irradiance_for_period()` below.
    """
    settings = get_settings()
    params = _build_query_params(latitude, longitude, year, attributes, interval, leap_day, utc)
    response = _curl_get(
        settings.nrel_nsrdb_base_url,
        params=params,
        timeout=settings.nrel_request_timeout_seconds,
    )
    response.raise_for_status()
    return response


@trace_tool(name="nrel_nsrdb_csv_download")
def download_nsrdb_csv(download_url: str) -> str:
    """GET the actual CSV body from an NREL-provided download link.

    The link points to a ZIP archive bundling the CSV (not raw CSV text), and
    can briefly 403/404 before the async export job finishes uploading —
    both handled here.
    """
    settings = get_settings()
    last_exc: Optional[Exception] = None
    for delay in (0, *DOWNLOAD_RETRY_DELAYS_SECONDS):
        if delay:
            time.sleep(delay)
        try:
            response = _curl_get(download_url, timeout=settings.nrel_request_timeout_seconds)
            response.raise_for_status()
            return _unwrap_csv(response)
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in (403, 404):
                raise
            last_exc = exc  # likely the export job hasn't finished uploading yet — retry
    raise last_exc


def _unwrap_csv(response: requests.Response) -> str:
    """Return CSV text, unzipping first if NREL bundled the CSV in a ZIP archive."""
    content_type = response.headers.get("Content-Type", "")
    if "zip" in content_type or response.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not csv_names:
                raise ValueError(f"NREL ZIP download had no CSV inside it: {archive.namelist()}")
            return archive.read(csv_names[0]).decode("utf-8")
    return response.text


# ── Parsing — no network I/O, so not a tool span ────────────────────────────

def parse_nsrdb_records(csv_text: str) -> list[dict]:
    """Parse an NSRDB CSV export into hourly records.

    NSRDB CSVs have a 2-row site metadata header, then a data header row, then
    one row per timestep (Year, Month, Day, Hour, Minute, GHI, DNI, ...).
    Numeric fields are coerced to float/int; anything else is left as a string.
    """
    rows = list(csv.reader(io.StringIO(csv_text)))
    if len(rows) < 3:
        return []
    header = rows[2]
    records = []
    for row in rows[3:]:
        if not row or len(row) != len(header):
            continue
        record: dict = {}
        for key, value in zip(header, row):
            try:
                record[key] = float(value) if "." in value else int(value)
            except ValueError:
                record[key] = value
        records.append(record)
    return records


def _extract_csv_text(response: requests.Response) -> str:
    """Return CSV text whether NREL answered synchronously or via a downloadUrl."""
    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type:
        payload = response.json()
        download_url = payload.get("outputs", {}).get("downloadUrl")
        if not download_url:
            raise ValueError(f"NREL response had no downloadUrl: {payload}")
        return download_nsrdb_csv(download_url)
    return response.text


# ── Public entry point — lat/lon + time period -> monthly-filtered records ──

def get_irradiance_for_period(
    latitude: float,
    longitude: float,
    year: int,
    start_month: int = 1,
    end_month: int = 12,
    attributes: Optional[list[str]] = None,
) -> list[dict]:
    """Fetch NSRDB hourly records for a site/year, filtered to [start_month, end_month]."""
    response = fetch_nsrdb_data(latitude, longitude, year, attributes=attributes)
    csv_text = _extract_csv_text(response)
    records = parse_nsrdb_records(csv_text)
    return [record for record in records if start_month <= record.get("Month", 0) <= end_month]
