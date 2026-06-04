from __future__ import annotations

import base64
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


DEFAULT_INDEX_NAME = "windows-persistence-registry"
DEFAULT_BATCH_SIZE = 500
DEFAULT_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

REQUIRED_REGISTRY_FIELDS = (
    "reg.key.path",
    "reg.key.name",
    "@timestamp",
    "file.name",
    "file.path",
    "host.name",
)

KEYWORD_FIELD = {"type": "keyword", "ignore_above": 8192}

INDEX_DEFINITION: dict[str, Any] = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "mapping.total_fields.limit": 1000,
        }
    },
    "mappings": {
        "dynamic": True,
        "properties": {
            "@timestamp": {"type": "date", "format": "strict_date_optional_time||yyyy-MM-dd'T'HH:mm:ss"},
            "host.name": {"type": "keyword"},
            "reg.key.path": KEYWORD_FIELD,
            "reg.key.name": KEYWORD_FIELD,
            "file.name": KEYWORD_FIELD,
            "file.path": KEYWORD_FIELD,
        },
    },
}


class OpenSearchError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def validate_registry_record(record: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_REGISTRY_FIELDS if _is_empty(record.get(field))]
    if missing:
        raise ValueError(f"Registry record is missing required fields: {', '.join(missing)}")


def _is_empty(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip() == ""

    return False


def stable_document_id(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("host.name", "")),
        str(record.get("reg.key.path", "")),
        str(record.get("reg.key.name", "")),
        str(record.get("file.name", "")),
        json.dumps(record.get("file.path", ""), ensure_ascii=False, sort_keys=True),
        str(record.get("@timestamp", "")),
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest


def iter_registry_records(input_file: Path) -> Iterable[dict[str, Any]]:
    with input_file.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {input_file}:{line_number}: {exc}") from exc

            if not isinstance(record, dict):
                raise ValueError(f"Expected JSON object in {input_file}:{line_number}")

            validate_registry_record(record)
            yield record


def build_bulk_payload(records: Iterable[dict[str, Any]], index_name: str) -> bytes:
    lines: list[str] = []

    for record in records:
        validate_registry_record(record)
        metadata = {"index": {"_index": index_name, "_id": stable_document_id(record)}}
        lines.append(json.dumps(metadata, ensure_ascii=False, separators=(",", ":")))
        lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True))

    if not lines:
        return b""

    return ("\n".join(lines) + "\n").encode("utf-8")


def batched(records: Iterable[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")

    batch: list[dict[str, Any]] = []
    for record in records:
        batch.append(record)
        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


class OpenSearchClient:
    def __init__(
        self,
        base_url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        verify_tls: bool = True,
        timeout: int = 30,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.retries = retries
        self.context = None if verify_tls else ssl._create_unverified_context()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any] | None:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})

        if self.username is not None and self.password is not None:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
            request_headers["Authorization"] = f"Basic {token}"

        for attempt in range(self.retries + 1):
            request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
                    payload = response.read()
                    if response.status not in expected:
                        raise OpenSearchError(
                            f"OpenSearch returned HTTP {response.status} for {method} {path}: {payload[:500]!r}",
                            response.status,
                        )
                    return _decode_json(payload)
            except urllib.error.HTTPError as exc:
                error_body = exc.read()
                if exc.code in expected:
                    return _decode_json(error_body)
                if exc.code in RETRY_STATUS_CODES and attempt < self.retries:
                    _sleep_before_retry(attempt)
                    continue
                raise OpenSearchError(
                    f"OpenSearch returned HTTP {exc.code} for {method} {path}: {error_body[:500]!r}",
                    exc.code,
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < self.retries:
                    _sleep_before_retry(attempt)
                    continue
                raise OpenSearchError(f"Could not connect to OpenSearch at {self.base_url}: {exc}") from exc

        raise OpenSearchError(f"OpenSearch request failed after {self.retries + 1} attempts: {method} {path}")

    def ensure_index(self, index_name: str = DEFAULT_INDEX_NAME) -> None:
        self.request("HEAD", f"/{index_name}", expected=(200, 404), headers={"Content-Type": "application/json"})

        try:
            self.request("HEAD", f"/{index_name}", expected=(200,))
            return
        except OpenSearchError as exc:
            if exc.status != 404:
                raise

        body = json.dumps(INDEX_DEFINITION, ensure_ascii=False).encode("utf-8")
        self.request("PUT", f"/{index_name}", body=body, expected=(200,))

    def bulk(self, payload: bytes) -> int:
        if not payload:
            return 0

        response = self.request(
            "POST",
            "/_bulk",
            body=payload,
            headers={"Content-Type": "application/x-ndjson"},
            expected=(200,),
        )
        return parse_bulk_response(response)


def _decode_json(payload: bytes) -> dict[str, Any] | None:
    if not payload:
        return None

    decoded = json.loads(payload.decode("utf-8"))
    return decoded if isinstance(decoded, dict) else None


def _sleep_before_retry(attempt: int) -> None:
    time.sleep(min(2**attempt, 8))


def parse_bulk_response(response: dict[str, Any] | None) -> int:
    if not response:
        return 0

    items = response.get("items")
    if not isinstance(items, list):
        raise OpenSearchError("OpenSearch bulk response did not include an items array")

    failures: list[str] = []
    indexed = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        result = item.get("index")
        if not isinstance(result, dict):
            continue

        status = int(result.get("status", 0))
        if status >= 400:
            failures.append(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            indexed += 1

    if failures:
        sample = "; ".join(failures[:3])
        raise OpenSearchError(f"OpenSearch bulk indexing failed for {len(failures)} documents: {sample}")

    return indexed


def index_registry_file(
    input_file: Path,
    *,
    opensearch_url: str,
    index_name: str = DEFAULT_INDEX_NAME,
    username: str | None = None,
    password: str | None = None,
    verify_tls: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
    retries: int = DEFAULT_RETRIES,
) -> int:
    client = OpenSearchClient(
        opensearch_url,
        username=username,
        password=password,
        verify_tls=verify_tls,
        retries=retries,
    )
    client.ensure_index(index_name)

    indexed = 0
    for batch in batched(iter_registry_records(input_file), batch_size):
        payload = build_bulk_payload(batch, index_name)
        indexed += client.bulk(payload)

    return indexed
