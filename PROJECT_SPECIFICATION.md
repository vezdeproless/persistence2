# Windows Persistence Detection Module Specification

## 1. Purpose

Windows Persistence Detection Module is a coursework project for collecting and analyzing Windows registry persistence artifacts. The project acquires raw artifacts from Windows 10 and Windows 11 virtual machines without shutting them down, transfers those artifacts to Ubuntu 22.04, normalizes registry evidence into `Registry.json`, and indexes the resulting records into OpenSearch.

The analyst performs investigation in OpenSearch Dashboards. The main analytical technique is frequency analysis over indexed registry records. By grouping records by executable path, registry location, or exact persistence entry, the analyst can identify rare commands and unusual registry persistence locations.

## 2. Target Lab

The expected lab contains three virtual machines:

- Windows 10 target.
- Windows 11 target.
- Ubuntu 22.04 processing and analysis server.

The physical host computer running VMware Workstation is also part of the analyst access path. OpenSearch Dashboards must be reachable from the physical host browser through the VMware network:

```text
Host computer browser
  -> VMware network
  -> Ubuntu VM
  -> OpenSearch Dashboards
```

Recommended Ubuntu resources:

- 4 CPU cores.
- 8 GiB RAM.
- 60 GiB disk.

The Windows targets must reach the Ubuntu server over SSH. The Ubuntu server runs OpenSSH Server, Python 3, RECmd, OpenSearch, and OpenSearch Dashboards.
The host computer must reach the Ubuntu server on TCP port `5601` for OpenSearch Dashboards.

## 3. Final Data Flow

```text
Windows 10 / Windows 11 target
  -> VSS acquisition
  -> local staging directory
  -> SCP upload
  -> Ubuntu processing server
  -> RECmd extraction
  -> registry normalization
  -> processed/Registry.json
  -> OpenSearch index windows-persistence-registry
  -> OpenSearch Dashboards
  -> physical host browser over the VMware network
```

The project creates one analytical output file:

```text
processed/Registry.json
```

`Registry.json` is newline-delimited JSON. Each line is one normalized registry value record. No additional frequency-analysis files are generated.

## 4. Directory Structure

```text
windows-persistence-detection/
  PROJECT_SPECIFICATION.md
  README.md
  pyproject.toml
  docs/
    architecture.md
    lab-setup.md
    EXECPLAN.md
  opensearch/
    index/
      windows-persistence-registry.json
    monitors/
      suspicious-executable-paths.json
      rare-executable-paths.json
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
    test_extract.py
    test_normalize.py
    test_opensearch.py
```

## 5. Acquisition Layer

The acquisition layer is implemented by:

```text
scripts/windows/Acquire-PersistenceArtifacts.ps1
```

The script must be run from an elevated PowerShell session because creating a Volume Shadow Copy Service snapshot requires administrator privileges. The script creates a snapshot of the Windows system drive, copies locked registry hive files from the snapshot, writes a manifest, transfers the staging directory to Ubuntu through SCP, and removes the snapshot during cleanup.

### 5.1 Windows Requirements

Install or verify:

- PowerShell 5.1 or newer.
- OpenSSH Client.
- Administrator access.
- SSH private key for the Ubuntu upload account.

Check OpenSSH Client:

```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Client*'
ssh -V
scp
```

Install OpenSSH Client if needed:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

Create an SSH key if needed:

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519
```

### 5.2 Windows Acquisition Command

Run on the Windows target:

```powershell
PowerShell.exe -ExecutionPolicy Bypass -File .\scripts\windows\Acquire-PersistenceArtifacts.ps1 `
  -Server 192.168.56.20 `
  -RemoteUser analyst `
  -RemotePath /home/analyst/uploads `
  -SshKeyPath C:\Users\analyst\.ssh\id_ed25519 `
  -IncludeSysmon `
  -IncludeWmi
```

Important parameters:

- `-Server`: Ubuntu server IP address.
- `-RemoteUser`: Ubuntu SSH upload account.
- `-RemotePath`: destination upload directory.
- `-SshKeyPath`: private key used by `scp`.
- `-IncludeSysmon`: copies Sysmon EVTX if present.
- `-IncludeWmi`: exports WMI subscription artifacts.
- `-KeepLocalCopy`: keeps the Windows staging directory for debugging.

### 5.3 Uploaded Structure

The uploaded directory is named:

```text
<hostname>_<YYYYMMDDTHHMMSSZ>
```

Example:

```text
WIN10-LAB_20260519T120000Z
```

Expected contents:

```text
Reg/
  SOFTWARE
  SOFTWARE.LOG1
  SOFTWARE.LOG2
  SYSTEM
  SYSTEM.LOG1
  SYSTEM.LOG2
  SAM
  SECURITY
NTUSER/
  <username>.DAT
  <username>.LOG1
  <username>.LOG2
UsrClass/
  <username>.DAT
  <username>.LOG1
  <username>.LOG2
ScheduledTasks/
Services/
EventLogs/
WMI/
manifest.json
```

Some optional files may be absent. Missing optional transaction logs, scheduled tasks, event logs, or WMI classes do not invalidate the acquisition.

## 6. Ubuntu Base Setup

Install base packages:

```bash
sudo apt update
sudo apt install -y openssh-server python3 python3-venv git curl unzip jq ca-certificates gnupg
sudo systemctl enable --now ssh
```

Create the upload account and directory:

```bash
sudo adduser analyst
sudo install -d -o analyst -g analyst -m 0750 /home/analyst/uploads
```
sudo install -d -o gribunovbg -g gribunovbg -m 0750 /home/gribunovbg/uploads

Add the Windows public key to:

```text
/home/analyst/.ssh/authorized_keys
```

Get-Content C:\Users\test\.ssh\id_ed25519.pub

sudo mkdir -p /home/gribunovbg/.ssh
sudo touch /home/gribunovbg/.ssh/authorized_keys
sudo nano /home/gribunovbg/.ssh/authorized_keys

Fix permissions:

```bash
sudo chown -R gribunovbg:gribunovbg /home/gribunovbg/.ssh
sudo chmod 700 /home/gribunovbg/.ssh
sudo chmod 600 /home/gribunovbg/.ssh/authorized_keys
```

Verify SSH from Windows:

```powershell
ssh -i C:\Users\<user>\.ssh\id_ed25519 analyst@<UBUNTU_IP>
```

## 7. OpenSearch Deployment

The lab uses native Ubuntu 22.04 packages for OpenSearch and OpenSearch Dashboards. Services run under systemd on the Ubuntu analysis server.

Set the Linux kernel parameter required by OpenSearch:

```bash
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opensearch.conf
```

Add the official OpenSearch APT signing key and package repositories:

```bash
curl -o- https://artifacts.opensearch.org/publickeys/opensearch.pgp \
  | sudo gpg --dearmor -o /usr/share/keyrings/opensearch-keyring

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring] https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/opensearch-2.x.list

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring] https://artifacts.opensearch.org/releases/bundle/opensearch-dashboards/2.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/opensearch-dashboards-2.x.list
```

Install and start OpenSearch and OpenSearch Dashboards. Use a strong administrator password that satisfies OpenSearch security requirements:
# Замените 'MySecure_P@ssw0rd2024!' на ваш сложный пароль
sudo env OPENSEARCH_INITIAL_ADMIN_PASSWORD='MySecure_P@ssw0rd2024!' apt install -y opensearch opensearch-dashboards


```bash
sudo apt update
sudo env OPENSEARCH_INITIAL_ADMIN_PASSWORD='MySecure_P@ssw0rd2024!' apt install -y opensearch opensearch-dashboards
sudo systemctl enable --now opensearch
sudo systemctl enable --now opensearch-dashboards
```

Configure OpenSearch Dashboards for host-computer browser access through the VMware network. Keep OpenSearch itself on `localhost`; only Dashboards needs to listen on the Ubuntu VM network interfaces.

```bash
sudo cp /etc/opensearch-dashboards/opensearch_dashboards.yml \
  /etc/opensearch-dashboards/opensearch_dashboards.yml.bak

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
opensearch.password: "MySecure_P@ssw0rd2024!"
opensearch.ssl.verificationMode: none
EOF

sudo systemctl restart opensearch-dashboards
```

If Ubuntu firewall is enabled, allow Dashboards from the VMware network only:

```bash
sudo ufw allow from <VMWARE_SUBNET_CIDR> to any port 5601 proto tcp
sudo ufw status
```

Verify OpenSearch:

```bash
curl -k -u admin:'<admin-password>' https://localhost:9200
curl -k -u admin:'<admin-password>' https://localhost:9200/_cluster/health?pretty
```

Verify OpenSearch Dashboards:

```text
http://<UBUNTU_IP>:5601
```

This URL must be tested from the physical host computer browser, not only from inside the Ubuntu VM. If it is unreachable, verify the VMware network mode, the Ubuntu VM IP address, the `server.host` setting, service status, and the Ubuntu firewall.

The package installation uses the built-in OpenSearch security plugin. The included examples use HTTPS with the `admin` account and `--opensearch-insecure` because the default lab certificate is self-signed. For a protected deployment, replace the self-signed certificate with a trusted certificate and remove `--opensearch-insecure`.

## 8. RECmd

The project does not parse raw registry hive files by itself. It calls RECmd through a command path provided with `--recmd`.

The command must accept:

```text
-f <hive_path> --kn <branch> --json <output_dir> --jsonf <output_name> --recover true
```

 31  wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
   32  sudo dpkg -i packages-microsoft-prod.deb
   33  rm packages-microsoft-prod.deb
   34  sudo apt update
   35  sudo apt install dotnet-runtime-9.0
   36  dotnet --info
   37  sudo tee /usr/local/bin/recmd >/dev/null <<'EOF'
#!/bin/sh
exec dotnet /opt/eztools/RECmd/RECmd/RECmd.dll "$@"
EOF

   38  sudo chmod 0755 /usr/local/bin/recmd
   42  find / -name dotnet 2>/dev/null
   44  sudo mkdir -p /opt/eztools/RECmd
   45  cd /tmp
   46  curl -L -o RECmd.zip https://download.ericzimmermanstools.com/net9/RECmd.zip
   47  sudo unzip -o RECmd.zip -d /opt/eztools/RECmd
   48  find /opt/eztools/RECmd -iname 'RECmd.dll' -o -iname 'RECmd.exe'
   49  /usr/local/bin/recmd --help

### 8.1 Native .NET Wrapper

If RECmd is available as a .NET application:

```bash
sudo tee /usr/local/bin/recmd >/dev/null <<'EOF'
#!/bin/sh
exec dotnet /opt/eztools/RECmd/RECmd/RECmd.dll "$@"
EOF
sudo chmod 0755 /usr/local/bin/recmd
```

### 8.2 Wine Wrapper

If RECmd is available as a Windows executable:

```bash
sudo tee /usr/local/bin/recmd >/dev/null <<'EOF'
#!/bin/sh
exec wine /opt/RECmd/RECmd.exe "$@"
EOF
sudo chmod 0755 /usr/local/bin/recmd
```

Verify:

```bash
/usr/local/bin/recmd --help
```
sudo -u gribunovbg git clone https://github.com/vezdeproless/persistence2.git /home/gribunovbg/windows-persistence-detection

## 9. Processing Layer

The Python package is located under:

```text
src/persist_detector/
```

### 9.1 Modules

`cli.py` defines the command line interface. It exposes:

- `list-jobs`: prints planned RECmd extraction jobs.
- `extract`: runs RECmd and writes intermediate JSON.
- `normalize`: converts intermediate RECmd JSON into `Registry.json`.
- `index`: indexes an existing `Registry.json` into OpenSearch.
- `process`: runs extraction, normalization, and OpenSearch indexing.

`extract.py` discovers supported hives and builds RECmd commands. It searches:

- `Reg/SOFTWARE`
- `Reg/SYSTEM`
- `NTUSER/*.DAT`
- `UsrClass/*.DAT`

`targets.py` stores parent registry branches for extraction.

`normalize.py` reads RECmd JSON, recursively flattens `SubKeys`, emits one record per registry value, filters empty and numeric-only values, rewrites hive roots, converts timestamps, and writes only the thesis-required fields.

`opensearch.py` handles OpenSearch connectivity, index creation, mappings, validation, deterministic document IDs, bulk payload construction, retry handling, and indexing.

### 9.2 Full Workflow

```bash
UPLOAD=/home/gribunovbg/uploads/DESKTOP-T1I1MIS_20260603T221734Z
cd ~/windows-persistence-detection

PYTHONPATH=src python3 -m persist_detector process \
  --input "$UPLOAD" \
  --recmd /usr/local/bin/recmd \
  --opensearch-url https://localhost:9200 \
  --opensearch-username admin \
  --opensearch-password 'MySecure_P@ssw0rd2024!' \
  --opensearch-insecure
```

Expected output:

```text
Created extraction jobs: <N>
Wrote normalized registry records: <M>
Output: /home/analyst/uploads/WIN10-LAB_20260519T120000Z/processed/Registry.json
Indexed OpenSearch documents: <M>
OpenSearch index: windows-persistence-registry
```

### 9.3 Offline Processing

To write `Registry.json` without indexing:

```bash
PYTHONPATH=src python3 -m persist_detector process \
  --input "$UPLOAD" \
  --recmd /usr/local/bin/recmd \
  --skip-index
```

To index later:

```bash
PYTHONPATH=src python3 -m persist_detector index \
  --input "$UPLOAD/processed/Registry.json" \
  --opensearch-url https://localhost:9200 \
  --opensearch-username admin \
  --opensearch-password '<admin-password>' \
  --opensearch-insecure
```

### 9.4 CLI Options

Common processing options:

- `--input`: uploaded host directory.
- `--output`: custom `Registry.json` path.
- `--recmd`: RECmd executable or wrapper path.
- `--extracted-dir`: custom intermediate JSON directory.
- `--host`: manually set `host.name`.
- `--keep-extracted`: keep intermediate RECmd JSON.
- `--skip-index`: skip OpenSearch indexing.

OpenSearch options:

- `--opensearch-url`: base URL, default `https://localhost:9200` or `OPENSEARCH_URL`.
- `--opensearch-index`: index name, default `windows-persistence-registry`.
- `--opensearch-username`: username, default `OPENSEARCH_USERNAME`.
- `--opensearch-password`: password, default `OPENSEARCH_PASSWORD`.
- `--opensearch-insecure`: disable TLS certificate verification for self-signed lab clusters.
- `--opensearch-batch-size`: documents per bulk request, default `500`.
- `--opensearch-retries`: transient error retries, default `3`.

## 10. Registry.json Schema

Example record:

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

Field meanings:

- `@timestamp`: registry key last-write time converted to UTC-3.
- `host.name`: Windows host name from `manifest.json` or `--host`.
- `reg.key.path`: normalized registry key path.
- `reg.key.name`: final key name.
- `file.name`: registry value name.
- `file.path`: normalized file path extracted from registry value data when the value contains a command line; otherwise the trimmed registry value data.

No other fields are emitted by the normalizer or required by the OpenSearch index. Hive identity, source JSON file name, value type, user profile name, event metadata, and technique metadata are intentionally excluded from the thesis schema.

## 11. OpenSearch Index Design

The default index is:

```text
windows-persistence-registry
```

The index definition is stored in:

```text
opensearch/index/windows-persistence-registry.json
```

Important mappings:

- `@timestamp`: `date`
- `host.name`: `keyword`
- `reg.key.path`: `keyword`
- `reg.key.name`: `keyword`
- `file.name`: `keyword`
- `file.path`: `keyword`

`keyword` is used for the main analytical fields because analysts need exact filtering, wildcard filtering, terms aggregation, and sorting.

The Python ingestion layer creates the index automatically when it is missing. It uses deterministic document IDs based on host, key path, key name, value name, value data, and timestamp. Re-indexing the same `Registry.json` updates the same documents rather than creating duplicates.

## 12. OpenSearch Dashboards Workflow

### 12.1 Create Data View

In OpenSearch Dashboards:

1. Open Dashboards Management.
2. Create a Data View.
3. Use index pattern:

   ```text
   windows-persistence-registry
   ```

4. Select time field:

   ```text
   @timestamp
   ```

### 12.2 Verify Indexed Data

Open Discover and search:

```text
reg.key.path: *
```

Add columns:

- `@timestamp`
- `host.name`
- `reg.key.path`
- `file.name`
- `file.path`

Expected result: rows from `Registry.json` are visible as indexed OpenSearch documents.

### 12.3 Find Rare Executable Paths

Create a table visualization:

- Data View: `windows-persistence-registry`
- Bucket: terms
- Field: `file.path`
- Metric: count
- Sort: count ascending
- Size: 1000 or higher for a lab dataset

Interpretation:

- Low-count paths appear first.
- A path occurring once can be benign, but it deserves review before common operating system paths.
- Paths under user-writable locations such as `C:\Users\Public`, `AppData`, `Temp`, or `Downloads` are higher priority.

### 12.4 Find Rare Registry Locations

Create a table visualization:

- Bucket: terms
- Field: `reg.key.path`
- Metric: count
- Sort: count ascending

Use this to identify uncommon persistence locations before pivoting to exact values.

### 12.5 Investigate One Executable Path

In Discover:

```text
file.path: "C:\\Users\\Public\\course-test.exe"
```

Review:

- `reg.key.path`
- `file.name`
- `host.name`
- `@timestamp`

This shows exactly where the persistence value exists and when its parent key was last written.

### 12.6 Noisy Location Filters

COM and file association locations can produce many records. Inspect them separately.

COM-focused query:

```text
reg.key.path: (*Software*Classes*CLSID*)
```

File association command query:

```text
reg.key.path: (*Software*Classes*shell*command*)
```

### 12.7 Non-Noisy Persistence Filter

Use this query to focus on common persistence mechanisms without the two noisy groups:

```text
reg.key.path: (
  *Software*Microsoft*Active*Setup*Installed*Components*
  OR *Software*Microsoft*Command*Processor*
  OR *Software*Microsoft*Netsh*
  OR *Software*Microsoft*Office*
  OR *Software*Microsoft*Windows*CurrentVersion*Run*
  OR *Software*Microsoft*Windows*CurrentVersion*RunOnce*
  OR *Software*Microsoft*Windows*CurrentVersion*RunOnceEx*
  OR *Software*Microsoft*Windows*CurrentVersion*Winlogon*
  OR *Software*Microsoft*Windows NT*CurrentVersion*Image File Execution Options*
  OR *Software*Microsoft*Windows NT*CurrentVersion*SilentProcessExit*
  OR *Software*Microsoft*Windows NT*CurrentVersion*AppCompatFlags*
  OR *Software*Policies*Microsoft*Windows*System*Scripts*
  OR *System*ControlSet001*Services*
  OR *System*ControlSet001*Control*Session Manager*
  OR *System*ControlSet001*Control*Lsa*
  OR *System*ControlSet001*Control*Print*
  OR *System*Setup*
  OR *Environment*
  OR *Control Panel*Desktop*
)
```

After applying the filter, create a terms table on `file.path`, count ascending. This reproduces the main rare-artifact workflow directly over indexed `Registry.json`.

## 13. OpenSearch Alerting

Monitor templates are stored under:

```text
opensearch/monitors/
```

Templates:

- `suspicious-executable-paths.json`
- `rare-executable-paths.json`
- `suspicious-registry-locations.json`
- `uncommon-persistence-entries.json`

Deploy a monitor template with:

```bash
curl -X POST "https://localhost:9200/_plugins/_alerting/monitors" \
  -k -u admin:'<admin-password>' \
  -H "Content-Type: application/json" \
  --data-binary @opensearch/monitors/suspicious-executable-paths.json
```

The templates include empty `actions` arrays. Add notification destinations in OpenSearch Dashboards or by editing the JSON before deployment.

## 14. Validation

### 14.1 Unit Tests

Run:

```bash
python3 -m unittest
```

Expected result:

```text
Ran <N> tests in <time>s
OK
```

### 14.2 Registry.json Check

```bash
ls -lh "$UPLOAD/processed/Registry.json"
wc -l "$UPLOAD/processed/Registry.json"
head -1 "$UPLOAD/processed/Registry.json" | jq .
```

Expected result:

- file exists;
- line count is greater than zero on a normal Windows host;
- first line is valid JSON.

### 14.3 OpenSearch Check

```bash
curl -k -u admin:'<admin-password>' https://localhost:9200/windows-persistence-registry/_count?pretty
curl -k -u admin:'<admin-password>' 'https://localhost:9200/windows-persistence-registry/_search?q=reg.key.path:*&pretty'
```

Expected result:

- `_count` shows indexed documents;
- `_search` returns registry persistence records.

## 15. Troubleshooting

Problem: `process` prints `Wrote normalized registry records: 0`.

Check:

```bash
PYTHONPATH=src python3 -m persist_detector process \
  --input "$UPLOAD" \
  --recmd /usr/local/bin/recmd \
  --keep-extracted \
  --skip-index

find "$UPLOAD/processed/extracted" -type f | head
```

If no JSON files exist, check the RECmd wrapper. If JSON files exist but contain no `Values`, inspect whether the selected hive branch exists on that Windows host.

Problem: OpenSearch indexing fails.

Check:

```bash
curl -k -u admin:'<admin-password>' https://localhost:9200
curl -k -u admin:'<admin-password>' https://localhost:9200/_cluster/health?pretty
```

Then retry:

```bash
PYTHONPATH=src python3 -m persist_detector index \
  --input "$UPLOAD/processed/Registry.json" \
  --opensearch-url https://localhost:9200 \
  --opensearch-username admin \
  --opensearch-password '<admin-password>' \
  --opensearch-insecure
```

Problem: records are indexed but not visible in Discover.

Check:

- Data View index pattern is `windows-persistence-registry`.
- Time field is `@timestamp`.
- Time range includes the registry timestamps.
- Query is not filtering out the dataset.

## 16. Limitations

- RECmd is required for raw registry hive parsing.
- Frequency analysis quality improves with more hosts because rare and common values become easier to distinguish.
- OpenSearch monitor templates are starting points and should be tuned to the lab.
- VSS acquisition requires administrator privileges.
- Some registry values contain commands rather than literal file paths. The normalizer extracts a file path from common command lines when possible; otherwise `file.path` keeps the trimmed value data.

## 17. References

- OpenSearch Debian package installation: https://docs.opensearch.org/latest/install-and-configure/install-opensearch/debian/
- OpenSearch Dashboards Debian package installation: https://docs.opensearch.org/latest/install-and-configure/install-dashboards/debian/
- OpenSearch Bulk API: https://docs.opensearch.org/latest/api-reference/document-apis/bulk/
- OpenSearch Alerting API: https://docs.opensearch.org/latest/observing-your-data/alerting/api/
- OpenSearch Downloads: https://opensearch.org/downloads/
- RECmd project: https://github.com/EricZimmerman/RECmd
