# Windows Persistence Detection Module

Windows Persistence Detection Module collects persistence-related Windows registry artifacts from live Windows 10 and Windows 11 systems, processes raw registry hives on Ubuntu 22.04, writes normalized `Registry.json` NDJSON, and indexes the records into OpenSearch for analysis in OpenSearch Dashboards.

## Architecture

```text
Windows 10 / Windows 11 target
  -> VSS acquisition
  -> local staging
  -> SCP upload
  -> Ubuntu processing server
  -> RECmd extraction
  -> registry normalization
  -> processed/Registry.json
  -> OpenSearch index windows-persistence-registry
  -> OpenSearch Dashboards
  -> physical host browser over the VMware network
```

`Registry.json` is the only analytical output file. Frequency analysis is performed in OpenSearch Dashboards with terms aggregations and sorting, not by generating a secondary file.

## Repository Layout

- `scripts/windows/Acquire-PersistenceArtifacts.ps1` - Windows VSS acquisition and SCP transfer script.
- `src/persist_detector/` - Python extraction, normalization, and OpenSearch indexing package.
- `opensearch/index/windows-persistence-registry.json` - index settings and mappings.
- `opensearch/monitors/` - reusable OpenSearch Alerting monitor templates.
- `docs/architecture.md` - architecture and data model.
- `docs/lab-setup.md` - lab deployment steps.
- `PROJECT_SPECIFICATION.md` - authoritative self-contained project specification.
- `tests/` - focused unit tests.

## Windows Acquisition

Run from an elevated PowerShell session on a Windows target:

```powershell
PowerShell.exe -ExecutionPolicy Bypass -File .\scripts\windows\Acquire-PersistenceArtifacts.ps1 `
  -Server 192.168.56.20 `
  -RemoteUser analyst `
  -RemotePath /home/analyst/uploads `
  -SshKeyPath C:\Users\analyst\.ssh\id_ed25519 `
  -IncludeSysmon `
  -IncludeWmi
```

The script creates a VSS snapshot, copies registry hives and optional artifacts into a timestamped staging directory, transfers the directory to Ubuntu with SCP, and removes the local staging directory and VSS snapshot unless `-KeepLocalCopy` is used.

## Ubuntu Processing

List extraction jobs:

```bash
UPLOAD=/home/analyst/uploads/WIN10-LAB_20260519T120000Z
PYTHONPATH=src python3 -m persist_detector list-jobs --input "$UPLOAD"
```

Run the full processing workflow and index into OpenSearch:

```bash
export OPENSEARCH_URL=https://localhost:9200
export OPENSEARCH_USERNAME=admin
export OPENSEARCH_PASSWORD='<admin-password>'

PYTHONPATH=src python3 -m persist_detector process \
  --input "$UPLOAD" \
  --recmd /usr/local/bin/recmd \
  --opensearch-url "$OPENSEARCH_URL" \
  --opensearch-username "$OPENSEARCH_USERNAME" \
  --opensearch-password "$OPENSEARCH_PASSWORD" \
  --opensearch-insecure
```

Expected output:

```text
Created extraction jobs: <N>
Wrote normalized registry records: <M>
Output: /home/analyst/uploads/<host_timestamp>/processed/Registry.json
Indexed OpenSearch documents: <M>
OpenSearch index: windows-persistence-registry
```

To generate `Registry.json` without indexing, add `--skip-index`. To retry indexing later:

```bash
PYTHONPATH=src python3 -m persist_detector index \
  --input "$UPLOAD/processed/Registry.json" \
  --opensearch-url "$OPENSEARCH_URL" \
  --opensearch-username "$OPENSEARCH_USERNAME" \
  --opensearch-password "$OPENSEARCH_PASSWORD" \
  --opensearch-insecure
```

## OpenSearch Lab

Install OpenSearch and OpenSearch Dashboards natively on Ubuntu 22.04 from the official OpenSearch APT repositories:

```bash
sudo apt update
sudo apt install -y openssh-server python3 python3-venv git curl unzip jq ca-certificates gnupg
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opensearch.conf

curl -o- https://artifacts.opensearch.org/publickeys/opensearch.pgp \
  | sudo gpg --dearmor -o /usr/share/keyrings/opensearch-keyring

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring] https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/opensearch-2.x.list
echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring] https://artifacts.opensearch.org/releases/bundle/opensearch-dashboards/2.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/opensearch-dashboards-2.x.list

sudo apt update
sudo env OPENSEARCH_INITIAL_ADMIN_PASSWORD='<admin-password>' apt install -y opensearch opensearch-dashboards
sudo systemctl enable --now opensearch
sudo systemctl enable --now opensearch-dashboards

sudo sed -i \
  -e '/^server.host:/d' \
  -e '/^server.port:/d' \
  -e '/^opensearch.hosts:/d' \
  -e '/^opensearch.username:/d' \
  -e '/^opensearch.password:/d' \
  -e '/^opensearch.ssl.verificationMode:/d' \
  /etc/opensearch-dashboards/opensearch_dashboards.yml
sudo tee -a /etc/opensearch-dashboards/opensearch_dashboards.yml >/dev/null <<'EOF'
server.host: "0.0.0.0"
server.port: 5601
opensearch.hosts: ["https://localhost:9200"]
opensearch.username: "admin"
opensearch.password: "<admin-password>"
opensearch.ssl.verificationMode: none
EOF
sudo systemctl restart opensearch-dashboards
```

Verify:

```bash
curl -k -u admin:'<admin-password>' https://localhost:9200
curl -k -u admin:'<admin-password>' https://localhost:9200/_cluster/health?pretty
```

Open OpenSearch Dashboards:

```text
http://<UBUNTU_IP>:5601
```

Open this URL from the physical host computer browser. The Ubuntu VM must use a VMware network mode reachable from the host computer, and TCP port `5601` must be allowed if Ubuntu firewall is enabled. Create a Data View for `windows-persistence-registry` and use `@timestamp` as the time field.

## Frequency Analysis in Dashboards

Use Discover or Visualize to group `Registry.json` records directly in OpenSearch.

Rare executable path analysis:

- Data View: `windows-persistence-registry`
- Visualization: table
- Bucket: terms on `file.path`
- Metric: count
- Sort: count ascending

Example query:

```text
reg.key.path: (*Software*Microsoft*Windows*CurrentVersion*Run*)
```

Broader non-noisy persistence query:

```text
reg.key.path: (
  *Software*Microsoft*Active*Setup*Installed*Components*
  OR *Software*Microsoft*Command*Processor*
  OR *Software*Microsoft*Netsh*
  OR *Software*Microsoft*Windows*CurrentVersion*Run*
  OR *Software*Microsoft*Windows*CurrentVersion*RunOnce*
  OR *Software*Microsoft*Windows*CurrentVersion*Winlogon*
  OR *System*ControlSet001*Services*
  OR *System*ControlSet001*Control*Session*Manager*
  OR *Control*Panel*Desktop*
)
```

## Validation

Run local tests:

```bash
python3 -m unittest
```

The local tests validate command construction, normalization, the reduced registry schema, index mapping, bulk payload construction, and record validation. Full end-to-end validation requires the Windows and Ubuntu lab because VSS, SCP, RECmd, OpenSearch, and OpenSearch Dashboards are external runtime services.
