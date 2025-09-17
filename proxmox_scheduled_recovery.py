import os
import time
import sys

from proxmoxer import ProxmoxAPI

# ================================
# CONFIG
# ================================

PROXMOX_HOST = os.getenv("PROXMOX_HOST", "localhost")
PROXMOX_NODE = os.getenv("PROXMOX_NODE")
PROXMOX_USER = os.getenv("PROXMOX_USER", "root@pam")
PROXMOX_TOKEN_NAME = os.getenv("PROXMOX_TOKEN_NAME")
PROXMOX_TOKEN_VALUE = os.getenv("PROXMOX_TOKEN_VALUE")
PROXMOX_SSL_VERIFY = os.getenv("PROXMOX_SSL_VERIFY", False)

PROXMOX_DATASTORE = os.getenv("PROXMOX_DATASTORE")
PROXMOX_BACKUP_DATASTORE = os.getenv("PROXMOX_BACKUP_DATASTORE")

# ================================
# Validate CONFIG
# ================================
required_env_vars = [
    "PROXMOX_HOST", "PROXMOX_NODE", "PROXMOX_USER",
    "PROXMOX_TOKEN_NAME", "PROXMOX_TOKEN_VALUE",
    "PROXMOX_DATASTORE", "PROXMOX_BACKUP_DATASTORE"
]

for var in required_env_vars:
    if not globals()[var]:
        print(f"{var} is not set")
        sys.exit(1)

# ================================
# Connect to Proxmox API
# ================================

proxmox = ProxmoxAPI(
    PROXMOX_HOST,
    user=PROXMOX_USER,
    token_name=PROXMOX_TOKEN_NAME,
    token_value=PROXMOX_TOKEN_VALUE,
    verify_ssl=PROXMOX_SSL_VERIFY,
)


def get_vm_status(vmid):
    try:
        status = proxmox.nodes(PROXMOX_NODE).qemu(vmid).status.current.get()
        return status["status"]
    except Exception as e:
        print(f"Error fetching VM status: {e}")
        return None


def get_task_status(upid):
    try:
        task = proxmox.nodes(PROXMOX_NODE).tasks(upid).status.get()
        return task["status"]
    except Exception as e:
        print(f"Error fetching task status: {e}")
        return None


def wait_for_task(upid, *, timeout_seconds=600, initial_interval_seconds=5, max_interval_seconds=30):
    start_time = time.time()
    interval = max(0.5, float(initial_interval_seconds))
    while True:
        if time.time() - start_time > timeout_seconds:
            print("Timeout reached while waiting for task to complete.")
            return False
        status = get_task_status(upid)
        if status == "stopped":
            return True
        if status == "error":
            print("Task failed with status 'error'.")
            return False
        print("Task in progress...")
        time.sleep(interval)
        interval = min(interval * 1.5, max_interval_seconds)


def delete_vm(vmid, timeout=300):
    try:
        upid = proxmox.nodes(PROXMOX_NODE).qemu(vmid).delete()
        print(f"VM {vmid} deletion initiated.")

        if not upid:
            print("No UPID returned, cannot track task.")
            sys.exit(1)

        print(f"Tracking task with UPID: {upid}")

        ok = wait_for_task(upid, timeout_seconds=timeout)
        if not ok:
            print(f"VM {vmid} deletion failed or timed out.")
            sys.exit(1)
        print(f"VM {vmid} deletion completed.")

    except Exception as e:
        print(f"Error deleting VM: {e}")


def restore_vm(vmid, datastore, backup_file, timeout=600):
    try:
        upid = proxmox.nodes(PROXMOX_NODE).qemu.post(
            vmid=vmid, storage=datastore, archive=backup_file
        )
        print(f"VM {vmid} restore initiated from {backup_file}.")

        if not upid:
            print("No UPID returned, cannot track task.")
            sys.exit(1)

        print(f"Tracking task with UPID: {upid}")

        ok = wait_for_task(upid, timeout_seconds=timeout)
        if not ok:
            print(f"VM {vmid} restore failed or timed out.")
            sys.exit(1)
        print(f"VM {vmid} restore completed.")
        return upid

    except Exception as e:
        print(f"Error restoring VM: {e}")
        sys.exit(1)


# ================================
# Main Logic
# ================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: script.py <vmid>")
        sys.exit(1)

    VMID = int(sys.argv[1])
    status = get_vm_status(VMID)

    if status != "stopped":
        print(f"VM {VMID} is not stopped. Current status: {status}")
        sys.exit(1)
    else:
        print(f"VM {VMID} is stopped, proceeding...")

    # # Delete old VM
    delete_vm(VMID)

    backups = (
        proxmox.nodes(PROXMOX_NODE).storage(PROXMOX_BACKUP_DATASTORE).content.get()
    )
    vm_backups = [b for b in backups if b["vmid"] == VMID]

    if not vm_backups:
        print(f"No backups found for VM {VMID} in datastore {PROXMOX_BACKUP_DATASTORE}")
        sys.exit(1)

    # Pick the latest backup by timestamp
    latest_backup = sorted(vm_backups, key=lambda x: x["ctime"], reverse=True)[0]
    backup_file = latest_backup["volid"]

    print(f"Latest backup: {backup_file}")

    # Restore VM
    upid = restore_vm(VMID, PROXMOX_DATASTORE, backup_file)

    print("Restore completed successfully.")
