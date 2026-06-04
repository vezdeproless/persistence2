# Project Handoff

## Project Overview

Windows Persistence Detection Module is a coursework-oriented forensic pipeline for collecting Windows registry persistence artifacts from live Windows 10 and Windows 11 targets and analyzing them on Ubuntu 22.04 through OpenSearch and OpenSearch Dashboards.

The current architecture is:

```text
Windows 10 / Windows 11 target
  -> VSS acquisition
  -> local staging directory
  -> SCP upload
  -> Ubuntu processing server
  -> RECmd targeted extraction
  -> registry normalization
  -> processed/Registry.json
  -> OpenSearch index windows-persistence-registry
  -> OpenSearch Dashboards
  -> physical host browser over the VMware network
```

The project goal is to keep acquisition and analysis separated. The Windows endpoint only stages and transfers raw artifacts. Ubuntu runs RECmd and Python processing. OpenSearch stores normalized registry value records. OpenSearch Dashboards provides Discover, Data Views, filters, tables, terms aggregations, frequency analysis, and analyst investigation workflows. Dashboards is configured to listen on the Ubuntu VM network interface so the physical host browser can access `http://<UBUNTU_IP>:5601` through the VMware network.

Major technologies currently implemented:

- PowerShell 5.1 for Windows acquisition.
- Volume Shadow Copy Service for live raw hive acquisition.
- OpenSSH/SCP for transfer from Windows to Ubuntu.
- Python 3.10+ standard library for extraction orchestration, normalization, and OpenSearch ingestion.
- RECmd or a compatible wrapper for raw registry hive parsing.
- Native Ubuntu package deployment for OpenSearch and OpenSearch Dashboards.
- OpenSearch Bulk API for indexing `Registry.json`.
- OpenSearch Alerting monitor JSON templates.

Supported operating systems documented by the repository:

- Windows 10 target.
- Windows 11 target.
- Ubuntu 22.04 processing and analysis server.

## Repository Structure

Current file tree:

```text
AGENTS.md
PLANS.md
PROJECT_HANDOFF.md
PROJECT_SPECIFICATION.md
PROJECT_TODO.md
README.md
pyproject.toml
docs/
  EXECPLAN.md
  architecture.md
  lab-setup.md
opensearch/
  index/
    windows-persistence-registry.json
  monitors/
    rare-executable-paths.json
    suspicious-executable-paths.json
    suspicious-registry-locations.json
    uncommon-persistence-entries.json
scripts/
  windows/
    Acquire-PersistenceArtifacts.ps1
src/
  persist_detector/
    __init__.py
    __main__.py
    cli.py
    extract.py
    normalize.py
    opensearch.py
    targets.py
tests/
  __init__.py
  test_extract.py
  test_normalize.py
  test_opensearch.py
```

Important files and responsibilities:

- `scripts/windows/Acquire-PersistenceArtifacts.ps1`: Windows acquisition script. Requires an elevated PowerShell session. Creates a VSS snapshot, stages registry hives and optional artifacts, writes `manifest.json`, transfers the staging directory by SCP, and removes the VSS snapshot and local staging directory unless `-KeepLocalCopy` is used.
- `src/persist_detector/cli.py`: CLI entry point. Defines `extract`, `normalize`, `index`, `process`, `print-targets`, and `list-jobs`.
- `src/persist_detector/extract.py`: Discovers uploaded hive files and runs RECmd for configured parent branches.
- `src/persist_detector/normalize.py`: Converts RECmd JSON into `Registry.json` NDJSON.
- `src/persist_detector/opensearch.py`: OpenSearch ingestion layer. Handles index definition, record validation, stable document IDs, bulk payloads, HTTP requests, index creation, retry handling, and indexing.
- `src/persist_detector/targets.py`: Registry extraction branch lists.
- `opensearch/index/windows-persistence-registry.json`: JSON copy of the index definition used by Python.
- `opensearch/monitors/*.json`: OpenSearch Alerting monitor templates.
- `PROJECT_SPECIFICATION.md`: Current authoritative project specification.
- `README.md`: Concise usage guide.
- `docs/architecture.md`: Current architecture and data model.
- `docs/lab-setup.md`: Ubuntu, OpenSearch, RECmd, and processing setup notes.
- `docs/EXECPLAN.md`: Current implementation plan and design log.
- `tests/test_extract.py`: Verifies RECmd command construction uses `-f`.
- `tests/test_normalize.py`: Verifies flattening, filtering, field formatting, user hive root rewriting, and the reduced thesis schema.
- `tests/test_opensearch.py`: Verifies JSON artifacts, index mapping fields, mapping artifact parity, bulk payloads, record validation, and bulk response parsing.

CLI entry points:

- Package script from `pyproject.toml`: `persist-detector = "persist_detector.cli:main"`.
- Module entry point: `python3 -m persist_detector`.
- In source checkout, commands are documented with `PYTHONPATH=src python3 -m persist_detector ...`.

CLI commands currently implemented:

```text
extract       Run RECmd targeted extraction against uploaded hives.
normalize     Normalize RECmd JSON into Registry.json NDJSON.
index         Index an existing Registry.json file into OpenSearch.
process       Run extraction, normalization, and OpenSearch indexing.
print-targets Print configured registry extraction branches.
list-jobs     List RECmd extraction jobs for an uploaded host directory.
```

Current OpenSearch CLI options on `index` and `process`:

```text
--opensearch-url
--opensearch-index
--opensearch-username
--opensearch-password
--opensearch-insecure
--opensearch-batch-size
--opensearch-retries
```

## Current Implementation Status

Completed components:

- Windows VSS acquisition and SCP transfer: `scripts/windows/Acquire-PersistenceArtifacts.ps1`.
- Upload manifest generation with size and SHA-256 metadata: `scripts/windows/Acquire-PersistenceArtifacts.ps1`.
- Hive discovery for `Reg/SOFTWARE`, `Reg/SYSTEM`, `NTUSER/*.DAT`, and `UsrClass/*.DAT`: `src/persist_detector/extract.py`.
- RECmd command generation and execution: `src/persist_detector/extract.py`.
- Registry branch target lists for SOFTWARE, SYSTEM, NTUSER, and USRCLASS: `src/persist_detector/targets.py`.
- RECmd JSON recursive flattening: `src/persist_detector/normalize.py`.
- Empty, missing type, and numeric-only value filtering: `src/persist_detector/normalize.py`.
- Hive root rewriting for SOFTWARE, SYSTEM, NTUSER, and USRCLASS records: `src/persist_detector/normalize.py`.
- Timestamp conversion to UTC-3 string format: `src/persist_detector/normalize.py`.
- Reduced thesis schema output with only `reg.key.path`, `reg.key.name`, `@timestamp`, `file.name`, `file.path`, and `host.name`: `src/persist_detector/normalize.py`.
- OpenSearch index definition in Python: `src/persist_detector/opensearch.py`.
- OpenSearch mapping artifact: `opensearch/index/windows-persistence-registry.json`.
- OpenSearch Bulk API payload generation and stable document IDs: `src/persist_detector/opensearch.py`.
- OpenSearch HTTP client using Python standard library: `src/persist_detector/opensearch.py`.
- `process` workflow: extraction, normalization, optional cleanup, and OpenSearch indexing: `src/persist_detector/cli.py`.
- Standalone `index` command for retrying an existing `Registry.json`: `src/persist_detector/cli.py`.
- Four OpenSearch Alerting monitor templates: `opensearch/monitors/`.
- Fake RECmd end-to-end `process` integration coverage: `tests/test_process_cli.py`.
- Project specification and setup documentation: `PROJECT_SPECIFICATION.md`, `README.md`, `docs/architecture.md`, `docs/lab-setup.md`.
- Focused unit tests: `tests/`.

Partially completed components:

- OpenSearch Alerting monitor templates are present and syntactically valid JSON, but they have empty `actions` arrays and have not been validated against a live OpenSearch Alerting plugin instance.
- Native OpenSearch and OpenSearch Dashboards package deployment is documented for Ubuntu 22.04 with systemd services and the built-in security plugin.
- OpenSearch Dashboards external access from the physical host browser is documented through `server.host: "0.0.0.0"` and TCP port `5601`.
- Dashboard workflow is documented, but Data Views, saved searches, and visualizations are not represented as importable saved objects.
- End-to-end lab validation is not captured in tests because Windows VSS, SCP, RECmd runtime, OpenSearch, and OpenSearch Dashboards are external services.

Unfinished components:

- No integration test starts OpenSearch and verifies actual indexing into `windows-persistence-registry`.
- No validation command compares all monitor templates against OpenSearch Alerting API schema.
- No packaged release or installation workflow has been added beyond source checkout usage.
- No CI configuration exists.
- Optional non-registry artifacts collected by the Windows script, such as scheduled tasks, services metadata, Sysmon EVTX, and WMI JSON, are not normalized or indexed by the Python pipeline.

Planned components implied by current docs and code:

- Live OpenSearch indexing validation.
- Dashboard saved object export or scripted setup, if future requirements ask for importable dashboard assets.
- Monitor template deployment documentation with notification destination examples.
- Broader tests around CLI workflows and OpenSearch error paths.
- Optional processing for scheduled tasks, service metadata, Sysmon, and WMI artifacts if the project scope expands beyond registry records.

## Architecture Decisions

### OpenSearch as the analysis backend

Decision: The project stores normalized registry records in OpenSearch and uses OpenSearch Dashboards for analysis.

Rationale: The key analytical need is direct filtering, grouping, frequency analysis, and pivoting over `Registry.json` records. OpenSearch supports these operations natively with indexed documents and Dashboards terms aggregations.

Implementation location:

- `src/persist_detector/opensearch.py`
- `opensearch/index/windows-persistence-registry.json`
- `README.md`
- `PROJECT_SPECIFICATION.md`
- `docs/architecture.md`

### Registry.json is the only analytical output

Decision: The processing layer writes `processed/Registry.json` as the only analytical output file.

Rationale: Frequency analysis is performed by OpenSearch aggregations over indexed records. Keeping only `Registry.json` avoids duplicating analytical state and keeps the forensic handoff simple.

Implementation location:

- `src/persist_detector/cli.py`
- `src/persist_detector/normalize.py`
- `README.md`
- `PROJECT_SPECIFICATION.md`
- `docs/architecture.md`

### Windows endpoint only acquires raw artifacts

Decision: The Windows script does not produce detection reports.

Rationale: The architecture keeps analysis server-side. The Windows host stages raw registry hives and optional artifacts from a VSS snapshot, preserving evidence for Ubuntu-side parsing.

Implementation location:

- `scripts/windows/Acquire-PersistenceArtifacts.ps1`
- `docs/architecture.md`
- `PROJECT_SPECIFICATION.md`

### RECmd remains the raw registry hive parser

Decision: Python does not implement raw hive parsing; it calls RECmd or a compatible wrapper.

Rationale: Correct raw hive parsing, including transaction logs, is specialized. The Python code remains orchestration and normalization logic.

Implementation location:

- `src/persist_detector/extract.py`
- `docs/lab-setup.md`
- `PROJECT_SPECIFICATION.md`

### Parent branch extraction

Decision: RECmd is called for parent branches instead of hundreds of individual keys and values.

Rationale: Many target artifacts are registry values, while RECmd `--kn` extracts keys. Parent branch extraction preserves relevant values while keeping the number of RECmd calls manageable.

Implementation location:

- `src/persist_detector/targets.py`
- `src/persist_detector/extract.py`

### Standard-library OpenSearch client

Decision: OpenSearch ingestion uses `urllib` from the Python standard library instead of an external Python client.

Rationale: The project currently has no pip runtime dependencies and is easier to run in an isolated lab.

Implementation location:

- `src/persist_detector/opensearch.py`
- `pyproject.toml`

### Deterministic OpenSearch document IDs

Decision: Document IDs are SHA-256 hashes derived from host, key path, key name, value name, value data, and timestamp.

Rationale: Re-indexing the same `Registry.json` updates the same OpenSearch documents rather than creating duplicates.

Implementation location:

- `src/persist_detector/opensearch.py::stable_document_id`
- `tests/test_opensearch.py`

### Keyword mapping for analysis fields

Decision: Thesis schema fields `file.path`, `file.name`, `reg.key.path`, `reg.key.name`, and `host.name` are mapped as `keyword`.

Rationale: Analysts need exact filtering, wildcard filtering, terms aggregation, and sorting.

Implementation location:

- `src/persist_detector/opensearch.py::INDEX_DEFINITION`
- `opensearch/index/windows-persistence-registry.json`
- `tests/test_opensearch.py`

### Native Ubuntu OpenSearch services

Decision: OpenSearch and OpenSearch Dashboards are installed on Ubuntu 22.04 from the official OpenSearch APT repositories and run as systemd services. Dashboards binds to `0.0.0.0:5601` so the physical host computer can access the UI over the VMware network.

Rationale: Native packages keep deployment inside the Ubuntu analysis VM and preserve authenticated OpenSearch access.

Implementation location:

- `PROJECT_SPECIFICATION.md`
- `docs/lab-setup.md`
- `README.md`

## Data Flow

Actual implemented flow:

```mermaid
flowchart LR
    A["Acquire-PersistenceArtifacts.ps1"] --> B["VSS snapshot"]
    B --> C["C:\\ProgramData\\PersistenceCollector\\staging\\<host_timestamp>"]
    C --> D["scp upload"]
    D --> E["/home/analyst/uploads/<host_timestamp>"]
    E --> F["persist_detector extract / process"]
    F --> G["processed/extracted/*.json"]
    G --> H["persist_detector normalize / process"]
    H --> I["processed/Registry.json"]
    I --> J["persist_detector index / process"]
    J --> K["OpenSearch Bulk API"]
    K --> L["windows-persistence-registry"]
    L --> M["OpenSearch Dashboards on Ubuntu VM"]
    N["Physical host browser"] --> O["VMware network"]
    O --> M
```

`process` is the primary command. It computes:

```text
output = <input>/processed/Registry.json unless --output is provided
extracted_dir = <output_parent>/extracted unless --extracted-dir is provided
host_name = --host or manifest.json host_name
```

Then it runs:

1. `run_extraction(input, extracted_dir, recmd)`
2. `normalize_directory(extracted_dir, output, host_name=host_name)`
3. removes `extracted_dir` if records were written and `--keep-extracted` is not used
4. indexes `output` unless `--skip-index` is used

## Data Models

### Registry.json schema

`Registry.json` is NDJSON. Each line is one JSON object. Example:

```json
{
  "@timestamp": "2026-05-19T09:34:56",
  "file.name": "Updater",
  "file.path": "C:\\Users\\Public\\updater.exe",
  "host.name": "WIN10-LAB",
  "reg.key.name": "Run",
  "reg.key.path": "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
}
```

Required for OpenSearch indexing:

- `@timestamp`
- `reg.key.path`
- `reg.key.name`
- `file.name`
- `file.path`
- `host.name`

No other fields are emitted by the normalizer.

### Normalization behavior

Implemented in `src/persist_detector/normalize.py`:

- Reads RECmd JSON files with UTF-8 BOM tolerance.
- Recursively traverses dictionaries/lists and recognizes key-shaped nodes by `KeyPath`, `KeyName`, `Values`, or `SubKeys`.
- Processes each item in `Values` as a separate output record.
- Accepts value type keys: `ValueType`, `ValueTypeName`, `Type`, `DataType`.
- Accepts value name keys: `ValueName`, `Name`.
- Accepts value data keys: `ValueData`, `Data`, `Value`, `ValueDataRaw`, `DataRaw`.
- Accepts timestamp keys: `LastWriteTime`, `LastWriteTimestamp`, `LastWriteTimeUtc`, `Timestamp`.
- Drops records when value type is empty.
- Drops records when value data is empty.
- Drops records when value data is numeric-only.
- Trims string value data.
- Preserves list value data after recursively trimming strings.
- Sorts output JSON keys when writing lines.

### Field mappings from RECmd to Registry.json

- RECmd key path -> `reg.key.path`
- RECmd key name -> `reg.key.name`
- RECmd value name -> `file.name`
- RECmd value data -> `file.path`, with common command lines normalized to the referenced file path when possible
- RECmd key last-write timestamp -> `@timestamp`

### Hive root rewriting

Implemented by `normalize_key_path`:

- SOFTWARE root becomes `Software`.
- SYSTEM root becomes `System`.
- NTUSER root becomes `NTUSER.DAT-<username>`.
- USRCLASS root becomes `UsrClass-<username>`.
- `HKEY_LOCAL_MACHINE\SOFTWARE` and `HKEY_LOCAL_MACHINE\SYSTEM` are rewritten to normalized short roots.
- `HKEY_CURRENT_USER` paths are rewritten under the user hive root label.

### Timestamp behavior

`parse_timestamp`:

- Converts `Z` to `+00:00`.
- Replaces the first space with `T` when needed.
- Truncates overlong fractional seconds to six digits.
- Treats timezone-less parsed timestamps as UTC.
- Converts to UTC-3.
- Formats as `YYYY-MM-DDTHH:MM:SS`.

## OpenSearch Design

### Ingestion architecture

Implemented in `src/persist_detector/opensearch.py`.

The ingestion layer:

- Defines `DEFAULT_INDEX_NAME = "windows-persistence-registry"`.
- Defines `INDEX_DEFINITION`.
- Validates records before indexing.
- Generates stable document IDs.
- Builds OpenSearch Bulk API NDJSON payloads.
- Creates the index if missing.
- Sends bulk requests to `/_bulk`.
- Supports basic authentication.
- Supports disabling TLS verification with `--opensearch-insecure`.
- Retries transient HTTP/network failures for status codes `429`, `500`, `502`, `503`, and `504`.
- Parses bulk response item failures and raises an `OpenSearchError` with failure samples.

### Index names

Default index:

```text
windows-persistence-registry
```

The CLI can override it with:

```text
--opensearch-index
OPENSEARCH_INDEX
```

### Mappings

Mapping exists in two places and is currently covered by a parity test:

- Python: `src/persist_detector/opensearch.py::INDEX_DEFINITION`
- JSON artifact: `opensearch/index/windows-persistence-registry.json`

Key mapping choices:

- `@timestamp`: `date`, format `strict_date_optional_time||yyyy-MM-dd'T'HH:mm:ss`
- `host.name`: `keyword`
- `reg.key.path`, `reg.key.name`, `file.name`, `file.path`: `keyword` with `ignore_above: 8192`

### Alerting design

Implemented monitor templates under `opensearch/monitors/`:

- `suspicious-executable-paths.json`: query-level monitor for paths containing user-writable, temporary, URL, command interpreter, or screensaver indicators.
- `rare-executable-paths.json`: query-level monitor with a terms aggregation on `file.path`, ascending count order, and a bucket selector for count `<= 1`.
- `suspicious-registry-locations.json`: query-level monitor for high-interest registry locations such as Netsh, Image File Execution Options, SilentProcessExit, AppCompatFlags, LSA, and Control Panel Desktop.
- `uncommon-persistence-entries.json`: query-level monitor using `multi_terms` over `reg.key.path`, `file.name`, and `file.path`, with a bucket selector for count `<= 1`.

Implemented status:

- Files exist and are valid JSON.
- Tests assert at least five OpenSearch JSON artifacts are parseable.

Planned status:

- Templates have not been validated against a live OpenSearch Alerting API.
- Templates intentionally contain empty `actions` arrays.
- Notification destination setup is not implemented.

### Dashboard strategy

Implemented as documentation, not saved object automation.

Documented in:

- `README.md`
- `docs/architecture.md`
- `docs/lab-setup.md`
- `PROJECT_SPECIFICATION.md`

Current strategy:

- Create a Data View for `windows-persistence-registry`.
- Use `@timestamp` as the time field.
- Use Discover for raw investigation.
- Add columns `@timestamp`, `host.name`, `reg.key.path`, `reg.key.name`, `file.name`, and `file.path`.
- Use table visualizations with terms aggregation on `file.path` or `reg.key.path`.
- Sort count ascending to surface rare values first.

No saved object export currently exists.

## Remaining Work

The complete structured task list is in `PROJECT_TODO.md`.

Highest-impact remaining work:

- Run a real end-to-end lab validation against Windows acquisition, RECmd, OpenSearch, and OpenSearch Dashboards from the physical host browser.
- Validate monitor templates against a live OpenSearch Alerting API.
- Add documentation for secured OpenSearch deployment with authentication and TLS.
- Consider saved OpenSearch Dashboards objects if importable dashboards become a requirement.
- Decide whether optional collected artifacts should be normalized and indexed in future project scope.

## Known Issues

### No live OpenSearch test coverage

The OpenSearch ingestion layer is unit-tested for payload construction and response parsing, but no test starts OpenSearch or verifies actual indexing.

Affected files:

- `src/persist_detector/opensearch.py`
- `tests/test_opensearch.py`

### `ensure_index` performs two HEAD requests

`OpenSearchClient.ensure_index` first calls `HEAD /<index>` with expected `(200, 404)`, then calls `HEAD /<index>` again expecting `(200,)` and catches `404`. This is functionally acceptable but inefficient and should be simplified.

Affected file:

- `src/persist_detector/opensearch.py`

### Alerting monitors have no notification actions

Monitor templates define conditions but do not notify anywhere until an operator adds actions.

Affected files:

- `opensearch/monitors/rare-executable-paths.json`
- `opensearch/monitors/suspicious-executable-paths.json`
- `opensearch/monitors/suspicious-registry-locations.json`
- `opensearch/monitors/uncommon-persistence-entries.json`

### Monitor query syntax is not live-validated

The JSON is syntactically valid, but the repository does not confirm that the installed OpenSearch Alerting plugin accepts every monitor body as-is.

Affected files:

- `opensearch/monitors/*.json`
- `tests/test_opensearch.py`

### Optional collected artifacts are not processed

The Windows script can collect scheduled tasks, services metadata, Sysmon EVTX, and WMI JSON. The Python processing layer currently focuses on registry hives and does not index those optional artifacts.

Affected files:

- `scripts/windows/Acquire-PersistenceArtifacts.ps1`
- `src/persist_detector/cli.py`
- `src/persist_detector/normalize.py`

### No CI configuration

Tests are run manually. There is no GitHub Actions or other continuous integration configuration.

Affected files:

- `tests/`
- repository root, if CI is added

### No packaged install verification

The code defines a package script in `pyproject.toml`, but current docs primarily use `PYTHONPATH=src python3 -m persist_detector`. There is no test for installing the package into a virtual environment and invoking `persist-detector`.

Affected files:

- `pyproject.toml`
- `README.md`
- `docs/lab-setup.md`
- `PROJECT_SPECIFICATION.md`

## Recommended Continuation Plan

1. Read `PROJECT_SPECIFICATION.md`, `README.md`, and this file to understand the intended and actual architecture.
2. Run the existing test suite from the repository root:

   ```powershell
   & 'C:\Users\griboris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest
   ```

3. Inspect CLI help with:

   ```powershell
   $env:PYTHONPATH='src'
   & 'C:\Users\griboris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m persist_detector --help
   & 'C:\Users\griboris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m persist_detector process --help
   & 'C:\Users\griboris\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m persist_detector index --help
   ```

4. Start with the Critical tasks in `PROJECT_TODO.md`.
5. Improve tests and code without changing behavior by simplifying `ensure_index`.
6. Then validate against a live OpenSearch lab using the native Ubuntu services from `docs/lab-setup.md`.
7. After live validation, update `PROJECT_SPECIFICATION.md`, `README.md`, and `docs/lab-setup.md` with any command corrections.
8. Validate OpenSearch Alerting monitor deployment and update templates only after observing API responses.
9. Add saved Dashboard assets only if the project requirements explicitly require importable Dashboards objects.
10. Keep `Registry.json` as the only analytical output unless the project requirements are explicitly changed.
