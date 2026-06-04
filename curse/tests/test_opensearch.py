from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from persist_detector.opensearch import (
    DEFAULT_INDEX_NAME,
    INDEX_DEFINITION,
    build_bulk_payload,
    parse_bulk_response,
    stable_document_id,
    validate_registry_record,
)


def sample_record() -> dict[str, str]:
    return {
        "@timestamp": "2026-05-19T09:34:56",
        "host.name": "WIN10-LAB",
        "reg.key.path": "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        "reg.key.name": "Run",
        "file.name": "Updater",
        "file.path": "C:\\Users\\Public\\updater.exe",
    }


class OpenSearchTests(unittest.TestCase):
    def test_opensearch_json_artifacts_are_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        json_files = sorted((root / "opensearch").rglob("*.json"))

        self.assertGreaterEqual(len(json_files), 5)
        for path in json_files:
            with self.subTest(path=path):
                json.loads(path.read_text(encoding="utf-8"))

    def test_index_mapping_contains_required_fields(self) -> None:
        properties = INDEX_DEFINITION["mappings"]["properties"]

        self.assertEqual(properties["@timestamp"]["type"], "date")
        self.assertEqual(properties["host.name"]["type"], "keyword")
        self.assertEqual(properties["reg.key.path"]["type"], "keyword")
        self.assertEqual(properties["reg.key.name"]["type"], "keyword")
        self.assertEqual(properties["file.name"]["type"], "keyword")
        self.assertEqual(properties["file.path"]["type"], "keyword")
        self.assertEqual(
            set(properties),
            {"@timestamp", "host.name", "reg.key.path", "reg.key.name", "file.name", "file.path"},
        )

    def test_index_mapping_artifact_matches_python_definition(self) -> None:
        root = Path(__file__).resolve().parents[1]
        artifact = json.loads(
            (root / "opensearch" / "index" / "windows-persistence-registry.json").read_text(encoding="utf-8")
        )

        self.assertEqual(artifact, INDEX_DEFINITION)

    def test_build_bulk_payload_uses_stable_ids_and_ndjson(self) -> None:
        record = sample_record()
        payload = build_bulk_payload([record], DEFAULT_INDEX_NAME)
        lines = payload.decode("utf-8").splitlines()

        self.assertEqual(len(lines), 2)
        metadata = json.loads(lines[0])
        document = json.loads(lines[1])

        self.assertEqual(metadata["index"]["_index"], DEFAULT_INDEX_NAME)
        self.assertEqual(metadata["index"]["_id"], stable_document_id(record))
        self.assertEqual(document["file.path"], "C:\\Users\\Public\\updater.exe")

    def test_validate_registry_record_rejects_missing_required_field(self) -> None:
        record = sample_record()
        del record["file.path"]

        with self.assertRaises(ValueError):
            validate_registry_record(record)

    def test_parse_bulk_response_counts_successes_and_reports_failures(self) -> None:
        success = {"items": [{"index": {"status": 201}}, {"index": {"status": 200}}]}
        self.assertEqual(parse_bulk_response(success), 2)

        failure = {"items": [{"index": {"status": 400, "error": {"type": "mapper_parsing_exception"}}}]}
        with self.assertRaises(RuntimeError):
            parse_bulk_response(failure)


if __name__ == "__main__":
    unittest.main()
