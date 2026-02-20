import os
import json
import logging
from datetime import datetime
from filelock import FileLock

# Directory paths
BASE_DIR = "D:/INTRANET/Netinfo/Data"
LOG_DIR = "D:/INTRANET/Netinfo/Logs/Latest_Logs"
ARCHIVE_DIR = os.path.join(BASE_DIR, "Archives")

DEVICE_INVENTORY_FILE = os.path.join(BASE_DIR, "network_device_inventory.json")
DEVICE_CHANGES_FILE = os.path.join(LOG_DIR, "device_status_changes.json")
MAIN_DATA_FILE = os.path.join(BASE_DIR, "main_data.json")  # JSON-based main data

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# Logging settings (UTF-8 enabled)
current_date = datetime.now().strftime("%Y%m%d")
log_file_path = os.path.join(LOG_DIR, f"archive_{current_date}.log")
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

def log_message(message):
    """Log messages in UTF-8 and ensure English output."""
    try:
        english_message = message.replace("çalışmaya başladı", "Script started") \
                                 .replace("Günlük görev başlatılıyor", "Daily task started") \
                                 .replace("Günlük analiz sonucu boş", "No data processed") \
                                 .replace("Script tamamlandı ve kapanıyor", "Script completed and exiting.") \
                                 .replace("✅", "[SUCCESS]") \
                                 .replace("❌", "[ERROR]") \
                                 .replace("🔄", "[RUNNING]") \
                                 .replace("🛑", "[STOPPED]")
        print(english_message)
        logging.info(english_message)
    except UnicodeEncodeError:
        print("[ERROR] Logging error: Unable to encode message.")

def load_json_file(file_path):
    """Safely load JSON files with error handling."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_message(f"[ERROR] JSON load failed: {file_path} - {str(e)}")
            return None
    return None

def analyze_device_data():
    """Analyze and process network device data."""
    device_inventory = load_json_file(DEVICE_INVENTORY_FILE) or []
    main_data = load_json_file(MAIN_DATA_FILE) or {}

    daily_report = []

    for device in device_inventory:
        device_id = device.get("deviceid")
        hostname = device.get("hostname", "Unknown")
        serial = device.get("serial", "N/A")
        current_status = device.get("ping_state", "N/A")
        last_update = device.get("last_status_check", "N/A")

        # Count active/inactive ports
        device_ports = main_data.get(hostname, {}).get("ports", [])
        total_ports = len(device_ports)
        active_ports = sum(1 for port in device_ports if port["is_up"])
        inactive_ports = total_ports - active_ports

        # VLAN mapping
        vlan_map = {}
        vlan_list = set()
        for port in device_ports:
            vlan_id = port["vlan_id"] if port["vlan_id"] != "N/A" else "Unknown"
            vlan_list.add(vlan_id)
            port_status = "up" if port["is_up"] else "down"
            vlan_map.setdefault(vlan_id, []).append(f"{port['interface_name']} ({port_status})")

        # Prepare device report
        device_report = {
            "deviceid": device_id,
            "hostname": hostname,
            "serial": serial,
            "total_ports": total_ports,
            "active_ports": active_ports,
            "inactive_ports": inactive_ports,
            "vlans": vlan_map,
            "vlan_list": list(vlan_list),
            "last_update": last_update,
            "current_status": current_status
        }

        daily_report.append(device_report)

    log_message(f"[SUCCESS] Daily report generated: {len(daily_report)} devices processed.")
    return daily_report

def save_archive_data(data):
    """Save daily report to a JSON archive."""
    date_stamp = datetime.now().strftime("%Y%m%d")
    json_file = os.path.join(ARCHIVE_DIR, f"archive_{date_stamp}.json")

    try:
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        log_message(f"[SUCCESS] JSON report saved: {json_file}")
    except Exception as e:
        log_message(f"[ERROR] Failed to save report: {str(e)}")

def main():
    """Run the daily task."""
    log_message("[RUNNING] Daily task started.")
    daily_data = analyze_device_data()

    if not daily_data:
        log_message("[WARNING] No data processed.")
        return

    save_archive_data(daily_data)
    log_message("[SUCCESS] Daily task completed.")

if __name__ == "__main__":
    log_message("[RUNNING] Script started.")
    main()
    log_message("[STOPPED] Script completed and exiting.")
