import subprocess
import hashlib
import uuid as _uuid

def get_hwid():
    """
    Generates a unique hardware ID for the current machine.
    Tries to use Motherboard UUID and CPU ID for stability.
    """
    try:
        # Get Motherboard UUID
        cmd_uuid = 'wmic csproduct get uuid'
        uuid_out = subprocess.check_output(cmd_uuid, shell=True).decode().split('\n')
        hw_uuid = uuid_out[1].strip() if len(uuid_out) > 1 else ""

        # Get CPU ID
        cmd_cpu = 'wmic cpu get processorid'
        cpu_out = subprocess.check_output(cmd_cpu, shell=True).decode().split('\n')
        cpu_id = cpu_out[1].strip() if len(cpu_out) > 1 else ""

        if not hw_uuid or "Default" in hw_uuid or "None" in hw_uuid:
            # Fallback to MAC address based node ID
            hwid_raw = str(_uuid.getnode())
        else:
            hwid_raw = f"{hw_uuid}-{cpu_id}"
            
        return hashlib.sha256(hwid_raw.encode()).hexdigest().upper()
    except Exception:
        # Extreme fallback
        return hashlib.sha256(str(_uuid.getnode()).encode()).hexdigest().upper()

if __name__ == "__main__":
    print(f"Machine Hardware ID: {get_hwid()}")
