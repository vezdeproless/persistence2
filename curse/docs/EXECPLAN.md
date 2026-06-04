# Complete the OpenSearch architecture

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `PLANS.md` from the repository root.

## Purpose / Big Picture

The repository will contain a complete Windows registry persistence analysis project centered on OpenSearch. A student can acquire raw Windows artifacts, process them on Ubuntu, produce one `Registry.json` file, index it into `windows-persistence-registry`, and investigate the indexed records in OpenSearch Dashboards with filters and terms aggregations.

The observable result is a repeatable command sequence: run the Windows acquisition script, run `python3 -m persist_detector process` on the uploaded directory, confirm that `processed/Registry.json` exists, and confirm that documents appear in the OpenSearch index.

## Progress

- [x] (2026-06-03 00:00Z) Read the full OpenSearch architecture request from the attached task file.
- [x] (2026-06-03 00:00Z) Inspected the CLI, extraction, normalization, target mapping, tests, and documentation.
- [x] (2026-06-03 00:00Z) Added this OpenSearch implementation plan.
- [x] (2026-06-03 00:00Z) Added native OpenSearch indexing with index creation, mappings, validation, bulk indexing, deterministic document IDs, and retry handling.
- [x] (2026-06-03 00:00Z) Updated the CLI so `process` can run extraction, normalization, `Registry.json` generation, and OpenSearch indexing in one workflow.
- [x] (2026-06-03 00:00Z) Added OpenSearch deployment, index mapping, and monitor template artifacts.
- [x] (2026-06-03 00:00Z) Rewrote project documentation around the OpenSearch architecture.
- [x] (2026-06-03 00:00Z) Ran tests and repository-wide verification searches.

## Surprises & Discoveries

- Observation: The Python processor already used only the standard library.
  Evidence: `pyproject.toml` has no runtime dependencies and the processing modules import standard-library packages.
- Observation: The normalized thesis record model is intentionally minimal.
  Evidence: `normalize.py` emits only `reg.key.path`, `reg.key.name`, `@timestamp`, `file.name`, `file.path`, and `host.name`.

## Decision Log

- Decision: Use OpenSearch's REST API through Python standard-library `urllib`, not an external client package.
  Rationale: The lab can run without pip downloads. The needed operations are direct HTTP calls: create index, send bulk payloads, and report failures.
  Date/Author: 2026-06-03 / Codex
- Decision: Keep `Registry.json` as NDJSON on disk and make OpenSearch indexing an ingestion stage after normalization.
  Rationale: The on-disk file remains useful for audit and retry. It is also the only analytical output required by the architecture.
  Date/Author: 2026-06-03 / Codex
- Decision: Make `windows-persistence-registry` the default index name and provide the same mapping as both code and a JSON artifact under `opensearch/`.
  Rationale: The CLI can create the index automatically, while the standalone JSON file lets a student inspect or pre-create the index manually.
  Date/Author: 2026-06-03 / Codex
- Decision: Move frequency analysis into OpenSearch Dashboards terms aggregations.
  Rationale: The indexed registry records already contain the fields required for grouping by executable path, registry location, and value name. Dashboards can calculate counts and sort ascending without a second file.
  Date/Author: 2026-06-03 / Codex

## Outcomes & Retrospective

The OpenSearch architecture is implemented. The project now has one analytical output, `Registry.json`, and indexes that output into `windows-persistence-registry`. Documentation, deployment files, index mappings, monitor templates, CLI help, and tests describe the OpenSearch-centered workflow. Unit tests pass, CLI help exposes the expected OpenSearch options, and repository-wide searches do not find removed platform terminology or secondary-output artifacts.

## Context and Orientation

The repository contains a Windows acquisition script in `scripts/windows/Acquire-PersistenceArtifacts.ps1`, Python processing code in `src/persist_detector`, tests in `tests`, OpenSearch artifacts in `opensearch`, and documentation in `README.md`, `docs`, and `PROJECT_SPECIFICATION.md`.

The Windows script creates a Volume Shadow Copy Service snapshot, which is a Windows mechanism for reading consistent copies of locked files. It stages registry hives and optional artifacts, then transfers the staging directory to Ubuntu over SCP.

On Ubuntu, `src/persist_detector/extract.py` discovers uploaded hives and calls RECmd, a registry hive parser, for configured parent registry branches. `src/persist_detector/normalize.py` converts RECmd JSON into `Registry.json`, a newline-delimited JSON file where every line is one registry value record with the reduced thesis schema. `src/persist_detector/targets.py` stores extraction branches. `src/persist_detector/opensearch.py` creates the OpenSearch index and sends registry records through the Bulk API.

## Plan of Work

The code path is complete when the primary `process` command runs extraction, normalization, and indexing. The standalone `index` command must index an existing `Registry.json` so a student can retry indexing without repeating RECmd extraction.

The documentation is complete when `PROJECT_SPECIFICATION.md` explains the architecture, data flow, acquisition, RECmd usage, normalization model, OpenSearch integration, index design, monitor templates, dashboard usage, deployment, installation, configuration, CLI commands, expected outputs, limitations, and directory structure.

The OpenSearch artifacts are complete when native Ubuntu services provide OpenSearch and OpenSearch Dashboards, `opensearch/index/windows-persistence-registry.json` contains the mapping, and `opensearch/monitors` contains reusable monitor templates for suspicious paths, rare paths, suspicious registry locations, and uncommon persistence entries.

## Concrete Steps

Run commands from `C:\Saved Games\curse`.

Run tests:

    C:\Users\griboris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest

Expected result:

    Ran <N> tests in <time>s
    OK

Search for removed terminology:

    rg -n "<removed terms>"

Expected result: no matches in project content.

## Validation and Acceptance

The work is accepted when:

1. `python -m unittest` passes.
2. `process --help` shows OpenSearch options.
3. `index --help` is available for retrying existing `Registry.json` ingestion.
4. `process` writes `processed/Registry.json` and can index it into `windows-persistence-registry`.
5. OpenSearch index mappings and monitor templates exist under `opensearch/`.
6. `PROJECT_SPECIFICATION.md` describes the final OpenSearch architecture as the authoritative project specification.
7. Repository-wide searches find no removed platform terminology or secondary-output artifacts.

## Idempotence and Recovery

The Python processing step overwrites `processed/Registry.json` for the selected upload directory. OpenSearch bulk indexing uses deterministic document IDs derived from record content, so rerunning indexing for the same `Registry.json` updates the same documents instead of creating duplicates. If OpenSearch is unavailable, rerun the `index` command after the service is healthy. If RECmd extraction needs debugging, rerun `process` with `--keep-extracted` so intermediate JSON remains available.

## Artifacts and Notes

OpenSearch's Bulk API expects newline-delimited action and source lines. The index stage sends `index` actions to `/_bulk`. OpenSearch Alerting monitors are JSON documents sent to `_plugins/_alerting/monitors`. OpenSearch Dashboards frequency analysis uses a terms aggregation on `file.path` or `reg.key.path`, metric `Count`, and ascending count sort.

## Interfaces and Dependencies

The Windows script depends on built-in PowerShell 5.1, WMI/CIM, Volume Shadow Copy Service, and Windows OpenSSH `scp`.

The Ubuntu processor depends on Python 3.10 or newer, RECmd or a compatible wrapper, and network access to OpenSearch.

`src/persist_detector/opensearch.py` exposes:

    DEFAULT_INDEX_NAME = "windows-persistence-registry"
    INDEX_DEFINITION: dict[str, Any]
    validate_registry_record(record: dict[str, Any]) -> None
    stable_document_id(record: dict[str, Any]) -> str
    build_bulk_payload(records: Iterable[dict[str, Any]], index_name: str) -> bytes
    index_registry_file(...)

The CLI exposes:

    process --input <upload> --recmd <recmd> --opensearch-url <url>
    index --input <Registry.json> --opensearch-url <url>

Both commands support `--opensearch-index`, `--opensearch-username`, `--opensearch-password`, `--opensearch-insecure`, `--opensearch-batch-size`, and `--opensearch-retries`.
