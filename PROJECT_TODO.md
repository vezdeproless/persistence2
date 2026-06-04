# Project TODO

# Completed

## Task Name

End-to-end `process` integration test with fake RECmd

#### Status

Completed 2026-06-03. Added `tests/test_process_cli.py`, covering default extracted JSON cleanup and `--keep-extracted` preservation with a repository-local fake RECmd wrapper.

#### Verification

```text
python -m unittest
```

# Critical

## Task Name

Live OpenSearch indexing validation

#### Objective

Validate that the current OpenSearch ingestion layer can create `windows-persistence-registry` and index real NDJSON records into a running OpenSearch instance.

#### Files

- `src/persist_detector/opensearch.py`
- `README.md`
- `docs/lab-setup.md`
- `PROJECT_SPECIFICATION.md`
- optional new integration test under `tests/` if the test can be gated safely.

#### Dependencies

- Native OpenSearch and OpenSearch Dashboards services installed on Ubuntu 22.04.
- Existing `persist_detector index` command.

#### Suggested Implementation

Start the native services:

```bash
sudo systemctl start opensearch
sudo systemctl start opensearch-dashboards
```

Create a small temporary `Registry.json` with one valid normalized record. Run:

```bash
PYTHONPATH=src python3 -m persist_detector index \
  --input /tmp/Registry.json \
  --opensearch-url https://localhost:9200 \
  --opensearch-username admin \
  --opensearch-password '<admin-password>' \
  --opensearch-insecure
```

Verify:

```bash
curl -k -u admin:'<admin-password>' https://localhost:9200/windows-persistence-registry/_count?pretty
curl -k -u admin:'<admin-password>' 'https://localhost:9200/windows-persistence-registry/_search?q=reg.key.path:*&pretty'
```

If any command differs from the documentation, update the docs immediately.

#### Acceptance Criteria

- Index is created automatically.
- `_count` reports at least one document.
- `_search` returns the indexed record.
- Documentation commands match observed working commands.

## Task Name

Fix or simplify `ensure_index`

#### Objective

Remove the duplicate `HEAD` request in `OpenSearchClient.ensure_index` and make index existence handling easier to read and test.

#### Files

- `src/persist_detector/opensearch.py`
- `tests/test_opensearch.py`

#### Dependencies

- Existing `OpenSearchClient.request`.
- Existing `OpenSearchError.status`.

#### Suggested Implementation

Refactor `ensure_index` to do one existence check:

1. Send `HEAD /<index>`.
2. Return on `200`.
3. Create the index on `404`.
4. Re-raise any other error.

Because `urllib` turns HTTP errors into exceptions, keep behavior explicit. Add a unit test using a small fake client subclass or monkeypatch-style override of `request` to verify the sequence for existing and missing index cases.

#### Acceptance Criteria

- `ensure_index` no longer sends two HEAD requests for the normal existing-index path.
- Existing unit tests pass.
- New tests cover existing-index and missing-index behavior.

# High

## Task Name

Validate OpenSearch Alerting monitor templates against a live API

#### Objective

Confirm that every JSON monitor template under `opensearch/monitors/` is accepted by the OpenSearch Alerting API used in the lab environment.

#### Files

- `opensearch/monitors/rare-executable-paths.json`
- `opensearch/monitors/suspicious-executable-paths.json`
- `opensearch/monitors/suspicious-registry-locations.json`
- `opensearch/monitors/uncommon-persistence-entries.json`
- `PROJECT_SPECIFICATION.md`
- `docs/lab-setup.md`

#### Dependencies

- Running OpenSearch with Alerting plugin available.
- `windows-persistence-registry` index available.

#### Suggested Implementation

For each monitor:

```bash
curl -X POST "https://localhost:9200/_plugins/_alerting/monitors" \
  -k -u admin:'<admin-password>' \
  -H "Content-Type: application/json" \
  --data-binary @opensearch/monitors/<file>.json
```

Record the accepted monitor IDs. If the API rejects a body, adjust the template to match the installed Alerting plugin schema. Do not add notification actions unless there is a defined notification destination.

#### Acceptance Criteria

- All four monitor templates can be created through the API.
- Any required schema changes are committed.
- Documentation states how to deploy and remove the monitors.

## Task Name

Document secured OpenSearch deployment path

#### Objective

Add documentation for using authenticated and TLS-enabled OpenSearch with the native Ubuntu services.

#### Files

- `PROJECT_SPECIFICATION.md`
- `docs/lab-setup.md`
- `README.md`

#### Dependencies

- Current CLI support for `--opensearch-username`, `--opensearch-password`, and `--opensearch-insecure`.

#### Suggested Implementation

Add a section that clearly separates:

- current simplified lab mode;
- secured mode with credentials;
- when to use `--opensearch-insecure`;
- how to pass credentials through environment variables:

```bash
export OPENSEARCH_URL=https://localhost:9200
export OPENSEARCH_USERNAME=<user>
export OPENSEARCH_PASSWORD=<password>
```

Avoid adding untested deployment artifacts unless they are validated.

#### Acceptance Criteria

- Documentation explains both insecure lab mode and authenticated mode.
- CLI examples include environment variables and explicit options.
- No existing lab instructions are broken.

## Task Name

Add CLI error-path tests for OpenSearch options

#### Objective

Test argument validation for OpenSearch batch size and retry count, and test invalid Registry.json records before OpenSearch network calls.

#### Files

- `tests/test_opensearch.py`
- optional `tests/test_cli.py`
- `src/persist_detector/cli.py`
- `src/persist_detector/opensearch.py`

#### Dependencies

- Existing `run_opensearch_indexing`.
- Existing `validate_registry_record`.

#### Suggested Implementation

Add tests that call CLI functions directly with temporary files and fake args:

- `--opensearch-batch-size 0` exits with a clear error.
- `--opensearch-retries -1` exits with a clear error.
- A `Registry.json` line missing `file.path` raises `ValueError` before a bulk payload is created.

#### Acceptance Criteria

- Tests fail on invalid options.
- Error messages remain actionable.
- No OpenSearch service is required.

## Task Name

Check OpenSearch Dashboard workflow on a real dataset

#### Objective

Confirm that the documented OpenSearch Dashboards workflow works with indexed `Registry.json` records from at least one processed Windows upload and that Dashboards is reachable from the physical host computer browser through the VMware network.

#### Files

- `PROJECT_SPECIFICATION.md`
- `README.md`
- `docs/architecture.md`
- `docs/lab-setup.md`

#### Dependencies

- One completed Windows acquisition.
- RECmd installed through a wrapper.
- Running OpenSearch and OpenSearch Dashboards.
- Indexed `windows-persistence-registry` data.
- VMware network path from the physical host computer to the Ubuntu VM on TCP port `5601`.

#### Suggested Implementation

Follow the docs exactly:

1. Process one upload.
2. Open `http://<UBUNTU_IP>:5601` from the physical host computer browser.
3. Create Data View `windows-persistence-registry`.
4. Search `reg.key.path: *`.
5. Create a table grouped by `file.path`, sorted by count ascending.
6. Apply documented noisy and non-noisy registry location queries.

Update docs if any UI labels, query syntax, or steps differ.

#### Acceptance Criteria

- A student can reproduce a rare executable path table from the docs.
- The physical host computer browser can access OpenSearch Dashboards over the VMware network.
- At least one screenshot or observed transcript is summarized in documentation if screenshots are added later.
- Query examples are confirmed against the actual Dashboards query bar.

# Medium

## Task Name

Package installation verification

#### Objective

Verify that the project installs as a Python package and the `persist-detector` console script works outside `PYTHONPATH=src`.

#### Files

- `pyproject.toml`
- `README.md`
- `docs/lab-setup.md`
- optional new test or script under `tests/` or `scripts/`.

#### Dependencies

- Python 3.10+.
- Build backend behavior from setuptools.

#### Suggested Implementation

In a temporary virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
persist-detector --help
```

If installation fails, add the missing build-system metadata to `pyproject.toml`. If it succeeds, document the install path as an alternative to `PYTHONPATH=src`.

#### Acceptance Criteria

- `pip install .` succeeds in a clean venv.
- `persist-detector --help` works.
- Documentation includes either install instructions or states that source checkout execution is the supported mode.

## Task Name

Add CI test workflow

#### Objective

Run unit tests automatically on repository changes.

#### Files

- `.github/workflows/tests.yml` or another CI configuration appropriate to the repository host.
- `tests/`
- `README.md` if adding status instructions.

#### Dependencies

- Confirm repository host and CI availability.
- Existing test suite.

#### Suggested Implementation

If GitHub Actions is appropriate, add a workflow that uses Python 3.10 or newer and runs:

```bash
python -m unittest
```

Keep it minimal. Do not require OpenSearch for the default test job.

#### Acceptance Criteria

- CI runs the current unit tests.
- CI does not require external services.
- Workflow documentation is minimal and accurate.

## Task Name

Improve monitor template documentation

#### Objective

Document what each OpenSearch monitor template detects, what fields it uses, expected false positives, and how an analyst should tune it.

#### Files

- `PROJECT_SPECIFICATION.md`
- optional new `docs/opensearch-alerting.md`
- `opensearch/monitors/*.json`

#### Dependencies

- Current monitor templates.
- Live API validation task if schema changes are required.

#### Suggested Implementation

For each monitor, document:

- purpose;
- query logic;
- aggregation fields if applicable;
- trigger condition;
- known noisy cases;
- recommended tuning values;
- how to attach notification actions.

#### Acceptance Criteria

- Every monitor template has a matching explanation.
- Analysts can decide which templates to enable first.
- Documentation does not imply that empty actions send notifications.

## Task Name

Evaluate optional artifact indexing scope

#### Objective

Decide whether scheduled tasks, services metadata, Sysmon EVTX, or WMI artifacts should be processed in this project or explicitly remain out of scope.

#### Files

- `PROJECT_SPECIFICATION.md`
- `docs/architecture.md`
- `scripts/windows/Acquire-PersistenceArtifacts.ps1`
- possible future Python modules if scope expands.

#### Dependencies

- Current collector already stages optional artifacts.
- Current Python pipeline indexes registry records only.

#### Suggested Implementation

Do not implement new processors immediately. First write a short design note in `PROJECT_SPECIFICATION.md` or a new doc that lists:

- currently collected optional artifacts;
- current processing status;
- whether each artifact belongs in the same OpenSearch index or a separate index;
- schema implications.

Implement processors only after the scope decision is made.

#### Acceptance Criteria

- Project docs clearly state the status of optional artifacts.
- No reader expects scheduled tasks/services/Sysmon/WMI to appear in `windows-persistence-registry` unless implemented.

## Task Name

Add saved OpenSearch Dashboards objects only if required

#### Objective

Provide importable dashboard assets if the coursework requires ready-made dashboards instead of manual setup.

#### Files

- New directory such as `opensearch/dashboards/`.
- `README.md`
- `PROJECT_SPECIFICATION.md`
- `docs/lab-setup.md`

#### Dependencies

- Real OpenSearch Dashboards instance.
- Confirmed Data View and visualization configuration.

#### Suggested Implementation

First create the Data View and visualizations manually in Dashboards. Export saved objects from the UI. Commit the exported NDJSON only after import/export is tested on a fresh Dashboards instance.

#### Acceptance Criteria

- Saved objects import successfully into a fresh Dashboards instance.
- Manual setup instructions remain available.
- Documentation explains both import and manual creation paths.

# Low

## Task Name

Normalize documentation command style

#### Objective

Make command examples consistent across `README.md`, `docs/lab-setup.md`, `docs/architecture.md`, and `PROJECT_SPECIFICATION.md`.

#### Files

- `README.md`
- `docs/lab-setup.md`
- `docs/architecture.md`
- `PROJECT_SPECIFICATION.md`

#### Dependencies

- Completion of live validation tasks so commands are known-good.

#### Suggested Implementation

Use the same upload user, upload path, repo path, OpenSearch URL, and command format in all documents. Avoid conflicting examples.

#### Acceptance Criteria

- A student can copy commands in order without reconciling different usernames or paths.
- Any intentionally variable values are written as placeholders like `<UBUNTU_IP>`.

## Task Name

Add repository cleanup check

#### Objective

Provide a repeatable command or test to ensure generated `__pycache__` directories and other local artifacts are not committed.

#### Files

- possible `.gitignore`
- possible `scripts/cleanup.ps1` or docs-only command
- `README.md`

#### Dependencies

- Confirm whether this repository uses Git in the target environment.

#### Suggested Implementation

Add `.gitignore` entries for Python caches and common local outputs. If useful, document the PowerShell cleanup command already used during development:

```powershell
Get-ChildItem -Directory -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force
```

#### Acceptance Criteria

- Generated Python cache directories are ignored or easy to remove.
- Cleanup instructions do not delete user data.

Improve OpenSearch error messages

#### Objective

Make OpenSearch connection and bulk indexing errors easier for students to troubleshoot.

#### Files

- `src/persist_detector/opensearch.py`
- `src/persist_detector/cli.py`
- `README.md`
- `docs/lab-setup.md`

#### Dependencies

- Current `OpenSearchError` behavior.

#### Suggested Implementation

Catch `OpenSearchError` in CLI command handlers and print short next-step hints, such as checking `curl -k -u admin:'<admin-password>' https://localhost:9200` or using `--skip-index` to generate `Registry.json` offline. Preserve nonzero exit behavior.

#### Acceptance Criteria

- Failed indexing produces a concise actionable message.
- Tests cover at least one failure path if CLI handling changes.
