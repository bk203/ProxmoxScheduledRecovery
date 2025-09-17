import os
import time
import sys

from proxmoxer import ProxmoxAPI


def get_env(name, default=None):
    value = os.getenv(name, default)
    return value


def connect_proxmox():
    proxmox_host = get_env("PROXMOX_HOST", "localhost")
    proxmox_node = get_env("PROXMOX_NODE")
    proxmox_user = get_env("PROXMOX_USER", "root@pam")
    proxmox_token_name = get_env("PROXMOX_TOKEN_NAME")
    proxmox_token_value = get_env("PROXMOX_TOKEN_VALUE")
    proxmox_ssl_verify = get_env("PROXMOX_SSL_VERIFY", False)

    proxmox_datastore = get_env("PROXMOX_DATASTORE")
    proxmox_backup_datastore = get_env("PROXMOX_BACKUP_DATASTORE")

    required_env_vars = {
        "PROXMOX_HOST": proxmox_host,
        "PROXMOX_NODE": proxmox_node,
        "PROXMOX_USER": proxmox_user,
        "PROXMOX_TOKEN_NAME": proxmox_token_name,
        "PROXMOX_TOKEN_VALUE": proxmox_token_value,
        "PROXMOX_DATASTORE": proxmox_datastore,
        "PROXMOX_BACKUP_DATASTORE": proxmox_backup_datastore,
    }

    for var, val in required_env_vars.items():
        if val in (None, ""):
            print(f"{var} is not set")
            sys.exit(1)

    proxmox = ProxmoxAPI(
        proxmox_host,
        user=proxmox_user,
        token_name=proxmox_token_name,
        token_value=proxmox_token_value,
        verify_ssl=proxmox_ssl_verify,
    )

    return {
        "client": proxmox,
        "node": proxmox_node,
        "datastore": proxmox_datastore,
        "backup_datastore": proxmox_backup_datastore,
    }


def get_vm_status(proxmox, node, vmid):
    try:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        return status["status"]
    except Exception as e:
        print(f"Error fetching VM status: {e}")
        return None


def get_task_status(proxmox, node, upid):
    try:
        task = proxmox.nodes(node).tasks(upid).status.get()
        return task["status"]
    except Exception as e:
        print(f"Error fetching task status: {e}")
        return None


def wait_for_task(
    proxmox,
    node,
    upid,
    *,
    timeout_seconds=600,
    initial_interval_seconds=5,
    max_interval_seconds=30,
):
    start_time = time.time()
    interval = max(0.5, float(initial_interval_seconds))
    while True:
        if time.time() - start_time > timeout_seconds:
            print("Timeout reached while waiting for task to complete.")
            return False
        status = get_task_status(proxmox, node, upid)
        if status == "stopped":
            return True
        if status == "error":
            print("Task failed with status 'error'.")
            return False
        print("Task in progress...")
        time.sleep(interval)
        interval = min(interval * 1.5, max_interval_seconds)


def delete_vm(proxmox, node, vmid, timeout=300):
    try:
        upid = proxmox.nodes(node).qemu(vmid).delete()
        print(f"VM {vmid} deletion initiated.")

        if not upid:
            print("No UPID returned, cannot track task.")
            sys.exit(1)

        print(f"Tracking task with UPID: {upid}")

        ok = wait_for_task(proxmox, node, upid, timeout_seconds=timeout)
        if not ok:
            print(f"VM {vmid} deletion failed or timed out.")
            sys.exit(1)
        print(f"VM {vmid} deletion completed.")

    except Exception as e:
        print(f"Error deleting VM: {e}")


def restore_vm(proxmox, node, vmid, datastore, backup_file, timeout=600):
    try:
        upid = proxmox.nodes(node).qemu.post(
            vmid=vmid, storage=datastore, archive=backup_file
        )
        print(f"VM {vmid} restore initiated from {backup_file}.")

        if not upid:
            print("No UPID returned, cannot track task.")
            sys.exit(1)

        print(f"Tracking task with UPID: {upid}")

        ok = wait_for_task(proxmox, node, upid, timeout_seconds=timeout)
        if not ok:
            print(f"VM {vmid} restore failed or timed out.")
            sys.exit(1)
        print(f"VM {vmid} restore completed.")

    except Exception as e:
        print(f"Error restoring VM: {e}")
        sys.exit(1)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 1:
        print("Usage: proxmox-scheduled-recovery <vmid>")
        return 1

    vmid = int(argv[0])

    ctx = connect_proxmox()
    proxmox = ctx["client"]
    node = ctx["node"]
    datastore = ctx["datastore"]
    backup_datastore = ctx["backup_datastore"]

    status = get_vm_status(proxmox, node, vmid)

    if status != "stopped":
        print(f"VM {vmid} is not stopped. Current status: {status}")
        return 1
    else:
        print(f"VM {vmid} is stopped, proceeding...")

    delete_vm(proxmox, node, vmid)

    backups = proxmox.nodes(node).storage(backup_datastore).content.get()
    vm_backups = [b for b in backups if b.get("vmid") == vmid]

    if not vm_backups:
        print(f"No backups found for VM {vmid} in datastore {backup_datastore}")
        return 1

    latest_backup = sorted(vm_backups, key=lambda x: x["ctime"], reverse=True)[0]
    backup_file = latest_backup["volid"]

    print(f"Latest backup: {backup_file}")

    restore_vm(proxmox, node, vmid, datastore, backup_file)

    print("Restore completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
