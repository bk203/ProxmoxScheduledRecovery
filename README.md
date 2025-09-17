# Proxmox Scheduled Recovery

A simple script to automate the process of restoring backups in Proxmox VE.
We have an internal process that creates backups of VMs on a regular basis, using Proxmox Backup Server.
This script is designed to restore the latest backup of a specified VM or container on an offsite Proxmox VE server.
This way we can ensure that we have a recent copy of our VMs in case of a disaster.

```mermaid
---
config:
  theme: mc
title: Process
---
flowchart TD
    E@{ shape: circle, label: "VM 999" } --> A
    A[PVE Cluster A] -->|Backup Process| B(Proxmox Backup Server)
    C(Scheduled Recovery Script)  -->|Retrieves Backup| B
    C -->|Restore Process| D[PVE Cluster B]
    D --> F@{ shape: circle, label: "VM 999" }
```

## Features
- Automatically restores the latest backup of a specified VM or container.
- Configurable via command-line arguments.

## Requirements
- Proxmox VE API 2.0 or higher
- Python 3.9 or higher
- Requires API token with appropriate permissions
    - Datastore.Allocate
    - Datastore.AllocateSpace
    - SDN.Use
    - VM.Allocate
    - VM.Audit

## Configuration
Set the following environment variables for authentication:
- `PROXMOX_HOST`: Proxmox server hostname or IP address
- `PROXMOX_USER`: Proxmox username (e.g., `root@pam`)
- `PROXMOX_TOKEN_NAME`: API token name (only the name part, not the full `name@realm!tokenid`)
- `PROXMOX_TOKEN_VALUE`: API token value
- `PROXMOX_VERIFY_SSL`: Set to `True` to verify SSL certificates, `False` to skip verification (default: `False`)
- `PROXMOX_STORAGE`: Storage name where vm should be recovered to (e.g. `local`)
- `PROXMOX_BACKUP_STORAGE`: Storage name where backups are stored (e.g. `pbs02`)

## Usage
```bash
python proxmox_scheduled_recovery.py <vmid>
```

### On server example
```bash
# Install required tools
apt-get install python3-pip python3-venv
# Create a virtual environment
python3 -m venv ~/venvs/proxmox_recovery
# Activate the virtual environment
source ~/venvs/proxmox_recovery/bin/activate
# Export environment variables (can also be set in the venv's bin/activate script)
export PROXMOX_HOST="pve.example.com"
export PROXMOX_USER="root@pam"
...
# Install build package (if not already installed in the venv)
pip install proxmoxscheduledrecovery-0.1.0-py3-none-any.whl 
# Run the script for vm 999
proxmox_scheduled_recovery 999
```

Output:
```
VM 999 is stopped, proceeding...
VM 999 deletion initiated.
Tracking task with UPID: UPID:pve03:002BF047:132DF8C7:68CAD37C:qmdestroy:999:root@pam!ScheduledRecovery:
Task in progress...
Task in progress...
VM 999 deletion completed.
Latest backup: pbs02:backup/vm/999/2025-09-17T12:40:00Z
VM 999 restore initiated from pbs02:backup/vm/999/2025-09-17T12:40:00Z.
Tracking task with UPID: UPID:pve03:002BF069:132DFAEA:68CAD381:qmrestore:999:root@pam!ScheduledRecovery:
Task in progress...
Task in progress...
Task in progress...
VM 999 restore completed.
Restore completed successfully.
```

## Continuous Integration
GitHub Actions builds and lints this project on each push/PR using `uv` and `ruff`.
The workflow uploads `dist/` artifacts for download.

## Releases
Releases are automatically created when you push a tag like `1.0.0`.
The release workflow will:
- Build the package for all supported Python versions
- Create a GitHub release with the built artifacts attached
- Include installation instructions in the release notes

To create a release:
```bash
git tag 1.0.0
git push origin 1.0.0
```


## Dependencies
- [`proxmoxer`](https://github.com/proxmoxer/proxmoxer/): Python wrapper for Proxmox API v2
- [`requests`](https://pypi.org/project/requests/): HTTP library for Python
