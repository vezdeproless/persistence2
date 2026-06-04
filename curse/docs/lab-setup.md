# Lab Setup

This guide describes a minimal VMware lab:

- Windows 10 target.
- Windows 11 target.
- Ubuntu 22.04 processing and analysis server.
- Physical host computer running VMware Workstation and a browser.

OpenSearch Dashboards must be reachable from the physical host browser through the VMware network:

```text
Host computer browser -> VMware network -> Ubuntu VM -> OpenSearch Dashboards
```

Use a VMware network mode where the host can reach the Ubuntu VM IP address, such as host-only, bridged, or NAT with explicit port forwarding. Record the Ubuntu VM address as `<UBUNTU_IP>`.

## Ubuntu Base Packages

Install the required packages:

```bash
sudo apt update
sudo apt install -y openssh-server python3 python3-venv git curl unzip jq ca-certificates gnupg
sudo systemctl enable --now ssh
```

Verify:

```bash
systemctl status ssh --no-pager
python3 --version
```

## Upload Account and Directory

Create a dedicated user for SCP uploads:

```bash
sudo adduser analyst
sudo install -d -o analyst -g analyst -m 0750 /home/analyst/uploads
```

Add the Windows public SSH key to:

```text
/home/analyst/.ssh/authorized_keys
```

Set permissions:

```bash
sudo chown -R analyst:analyst /home/analyst/.ssh
sudo chmod 700 /home/analyst/.ssh
sudo chmod 600 /home/analyst/.ssh/authorized_keys
```

Verify from Windows:

```powershell
ssh -i C:\Users\<user>\.ssh\id_ed25519 analyst@<UBUNTU_IP>
```

## OpenSearch and OpenSearch Dashboards

Install OpenSearch and OpenSearch Dashboards natively on Ubuntu 22.04 from the official OpenSearch APT repositories. OpenSearch needs `vm.max_map_count` set on Linux:

```bash
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opensearch.conf
```

Add the OpenSearch signing key and package repositories:

```bash
curl -o- https://artifacts.opensearch.org/publickeys/opensearch.pgp \
  | sudo gpg --dearmor -o /usr/share/keyrings/opensearch-keyring

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring] https://artifacts.opensearch.org/releases/bundle/opensearch/2.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/opensearch-2.x.list

echo "deb [signed-by=/usr/share/keyrings/opensearch-keyring] https://artifacts.opensearch.org/releases/bundle/opensearch-dashboards/2.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/opensearch-dashboards-2.x.list
```

Install and start the services. Use a strong password that meets OpenSearch security requirements:

```bash
sudo apt update
sudo env OPENSEARCH_INITIAL_ADMIN_PASSWORD='<admin-password>' apt install -y opensearch opensearch-dashboards
sudo systemctl enable --now opensearch
sudo systemctl enable --now opensearch-dashboards
```

Configure OpenSearch Dashboards to listen on the Ubuntu VM network interfaces. Keep OpenSearch itself on `localhost`; only Dashboards needs browser access from the host computer.

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
opensearch.password: "<admin-password>"
opensearch.ssl.verificationMode: none
EOF

sudo systemctl restart opensearch-dashboards
```

If Ubuntu firewall is enabled, allow Dashboards from the VMware network. Replace `<VMWARE_SUBNET_CIDR>` with the host-only, bridged, or NAT subnet used by the lab, for example `192.168.56.0/24`.

```bash
sudo ufw allow from <VMWARE_SUBNET_CIDR> to any port 5601 proto tcp
sudo ufw status
```

Verify the service is listening beyond loopback:

```bash
sudo ss -ltnp | grep ':5601'
```

Verify OpenSearch:

```bash
curl -k -u admin:'<admin-password>' https://localhost:9200
curl -k -u admin:'<admin-password>' https://localhost:9200/_cluster/health?pretty
```

Find the Ubuntu VM IP address:

```bash
hostname -I
ip -4 addr
```

Verify OpenSearch Dashboards from inside the Ubuntu VM:

```bash
curl -I http://localhost:5601
```

Then verify OpenSearch Dashboards from the physical host computer browser:

```text
http://<UBUNTU_IP>:5601
```

If this URL is not reachable from the host computer, check the VMware network mode, confirm the host can reach `<UBUNTU_IP>`, confirm `server.host` is `0.0.0.0`, and confirm TCP port `5601` is allowed by the Ubuntu firewall.

## RECmd

The Python pipeline calls one executable path from `--recmd`. The command must accept RECmd-compatible arguments:

```text
-f <hive_path> --kn <branch> --json <output_dir> --jsonf <output_name> --recover true
```

If RECmd is launched through .NET, create a wrapper:

```bash
sudo mkdir -p /opt/eztools/RECmd
sudo tee /usr/local/bin/recmd >/dev/null <<'EOF'
#!/bin/sh
exec dotnet /opt/eztools/RECmd/RECmd/RECmd.dll "$@"
EOF
sudo chmod 0755 /usr/local/bin/recmd
```

If RECmd is launched through Wine, use:

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

## Process One Upload

Set the upload path:

```bash
UPLOAD=/home/analyst/uploads/<host_timestamp>
cd ~/windows-persistence-detection
```

List extraction jobs:

```bash
PYTHONPATH=src python3 -m persist_detector list-jobs --input "$UPLOAD"
```

Run the full workflow:

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

Expected files and index state:

```bash
ls -lh "$UPLOAD/processed/Registry.json"
wc -l "$UPLOAD/processed/Registry.json"
curl -k -u admin:'<admin-password>' https://localhost:9200/windows-persistence-registry/_count?pretty
```

## OpenSearch Dashboards Data View

Open OpenSearch Dashboards and create a Data View:

- Name: `windows-persistence-registry`
- Index pattern: `windows-persistence-registry`
- Time field: `@timestamp`

Use Discover to verify records:

```text
reg.key.path: *
```

Add table columns:

- `@timestamp`
- `host.name`
- `reg.key.path`
- `file.name`
- `file.path`
