"""Thin Meta Model API client: auth, bounded retries, timing, call guard, dry-run."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
RAW_DIR = OUT / "raw"
BASE_URL = "https://api.meta.ai/v1"
API_KEY_ENV = "META_API_KEY"
MAX_CALLS_PER_RUN = 3
MAX_RETRIES = 2
RETRY_STATUSES = frozenset({429, 500, 502, 503})  # 504: docs say the same request will usually time out again
MAX_BACKOFF_S = 60.0
TIMEOUT_S = 300.0

_DATA_URL = re.compile(r"^data:([\w/+.-]+);base64,(.*)$", re.S)


class CallBudgetExceeded(RuntimeError):
    """A run tried to send more requests than it is allowed."""


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status


@dataclass(frozen=True)
class ApiResult:
    body: dict[str, Any]
    latency_ms: float
    request_bytes: int
    retries: int


def data_url(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def output_text(body: dict[str, Any]) -> str:
    """Concatenate the output_text parts of a Responses API response."""
    return "\n".join(
        part.get("text", "")
        for item in body.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    )


def redact_payload(value: Any) -> Any:
    """Replace inline base64 media with a size + hash stub so a request can be printed."""
    if isinstance(value, dict):
        return {k: redact_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_payload(v) for v in value]
    if isinstance(value, str) and (m := _DATA_URL.match(value)):
        mime, b64 = m.groups()
        digest = sha256(b64.encode())[:12]
        return f"data:{mime};base64,<{len(b64):,} chars, sha256:{digest}>"
    return value


def _api_key() -> str:
    key = os.environ.get(API_KEY_ENV)
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == API_KEY_ENV:
                key = value.strip().strip("'\"")
    if not key:
        raise SystemExit(f"{API_KEY_ENV} is not set (export it or put it in {env_file.name}).")
    return key


def _backoff_s(attempt: int, response: httpx.Response) -> float:
    retry_after = response.headers.get("retry-after", "")
    if retry_after.replace(".", "", 1).isdigit():
        return min(float(retry_after), MAX_BACKOFF_S)
    return min(0.5 * 2**attempt + random.uniform(0, 0.25), MAX_BACKOFF_S)


def _save_raw(path: str, body: dict[str, Any]) -> None:
    """Keep every successful response body, so a parser bug never costs a second paid call."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    (RAW_DIR / f"{stamp}{path.replace('/', '_')}.json").write_text(json.dumps(body, indent=2))


class Client:
    """One instance per run. Counts requests and refuses to exceed `max_calls`."""

    def __init__(self, *, dry_run: bool, max_calls: int = MAX_CALLS_PER_RUN):
        self.dry_run = dry_run
        self.max_calls = max_calls
        self.calls_sent = 0
        self._http: httpx.Client | None = None
        if not dry_run:
            self._http = httpx.Client(
                base_url=BASE_URL,
                headers={"Authorization": f"Bearer {_api_key()}"},
                timeout=TIMEOUT_S,
            )

    def reserve(self, planned_calls: int) -> None:
        """Abort the run before anything is sent if its planned requests exceed the cap."""
        if self.calls_sent + planned_calls > self.max_calls:
            raise SystemExit(
                f"call guard: run needs {self.calls_sent + planned_calls} API calls; cap is {self.max_calls}"
            )

    def post_json(self, path: str, payload: dict[str, Any]) -> ApiResult | None:
        """POST JSON. In dry-run, print the request and return None."""
        if self.dry_run:
            self._print_request(path, {"Content-Type": "application/json"}, payload)
            return None
        body = json.dumps(payload).encode()
        return self._send(path, content=body, headers={"Content-Type": "application/json"})

    def post_file(self, path: str, fields: dict[str, str], file_path: Path) -> ApiResult | None:
        """POST multipart form data with one file part (sent last, as the docs advise)."""
        raw = file_path.read_bytes()
        if self.dry_run:
            stub = f"<{file_path.name}: {len(raw):,} bytes, sha256:{sha256(raw)[:12]}>"
            self._print_request(path, {"Content-Type": "multipart/form-data"}, {**fields, "file": stub})
            return None
        return self._send(path, data=fields, files={"file": (file_path.name, raw)}, size=len(raw))

    def _send(self, path: str, *, size: int | None = None, **request: Any) -> ApiResult:
        if self.calls_sent >= self.max_calls:
            raise CallBudgetExceeded(f"call guard: cap of {self.max_calls} calls reached")
        self.calls_sent += 1
        assert self._http is not None
        size = size if size is not None else len(request.get("content", b""))
        for attempt in range(MAX_RETRIES + 1):
            start = time.perf_counter()
            response = self._http.post(path, **request)
            if response.status_code < 400:
                latency_ms = (time.perf_counter() - start) * 1000
                body = response.json()
                _save_raw(path, body)
                return ApiResult(body, latency_ms, size, retries=attempt)
            if response.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
                raise ApiError(response.status_code, response.text)
            wait = _backoff_s(attempt, response)
            print(f"  HTTP {response.status_code}; retry {attempt + 1}/{MAX_RETRIES} in {wait:.1f}s")
            time.sleep(wait)
        raise AssertionError("unreachable")

    @staticmethod
    def _print_request(path: str, headers: dict[str, str], payload: dict[str, Any]) -> None:
        print(f"--- DRY RUN: POST {BASE_URL}{path}")
        for name, value in {"Authorization": "Bearer <redacted>", **headers}.items():
            print(f"{name}: {value}")
        print(json.dumps(redact_payload(payload), indent=2))
