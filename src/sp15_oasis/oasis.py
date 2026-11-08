"""Download one OASIS SingleZip CSV, slowly enough to stay inside the AUP."""

from __future__ import annotations

import csv
import io
import time
import zipfile
from urllib.parse import urlencode

import requests

API = "https://oasis.caiso.com/oasisapi/SingleZip"
USER_AGENT = "caiso-sp15-oasis/0.1 (research; github.com/AimePython/caiso-sp15-oasis)"


class OasisError(RuntimeError):
    pass


class OasisClient:
    def __init__(self, sleep_seconds: float = 7.0) -> None:
        self.sleep_seconds = sleep_seconds
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def fetch_csv(self, params: dict[str, str]) -> list[dict] | None:
        """Return CSV rows, or None when OASIS sends an XML 'no data' zip."""
        last_error: Exception | None = None
        for attempt in range(6):
            self._pace()
            url = API + "?" + urlencode(params, safe=",")
            try:
                response = self.session.get(url, timeout=180)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(10 * (attempt + 1))
                self._last = time.monotonic()
                continue
            self._last = time.monotonic()
            if response.status_code == 429 or b"Acceptable Use Policy" in response.content:
                time.sleep(15 * (attempt + 1))
                last_error = OasisError("CAISO rate limit")
                continue
            if response.status_code != 200:
                last_error = OasisError(
                    f"HTTP {response.status_code} for {params.get('queryname')} "
                    f"{params.get('startdatetime')}"
                )
                time.sleep(10)
                continue
            if response.content[:2] != b"PK":
                last_error = OasisError(
                    f"not a zip for {params.get('queryname')}: {response.content[:180]!r}"
                )
                time.sleep(10)
                continue
            try:
                return _rows_from_zip(response.content)
            except zipfile.BadZipFile as exc:
                last_error = exc
                time.sleep(10)
        raise OasisError(
            f"{params.get('queryname')} {params.get('startdatetime')} failed: {last_error}"
        )

    def _pace(self) -> None:
        if self._last == 0.0:
            return
        wait = self.sleep_seconds - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)


def _rows_from_zip(content: bytes) -> list[dict] | None:
    archive = zipfile.ZipFile(io.BytesIO(content))
    csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not csv_names:
        return None
    rows: list[dict] = []
    for name in csv_names:
        text = io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        for row in reader:
            cleaned = {
                (key or "").strip(): (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
                if key
            }
            rows.append(cleaned)
    return rows
