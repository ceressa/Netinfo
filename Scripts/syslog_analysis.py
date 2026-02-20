import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta

# 📂 File paths
DATA_FOLDER = "D:/INTRANET/Netinfo/Data"
LOG_FOLDER = "D:/INTRANET/Netinfo/Logs/Syslog_AI"

SYSLOG_RAW_FILE = os.path.join(DATA_FOLDER, "syslog_data.json")
MAIN_DATA_FILE = os.path.join(DATA_FOLDER, "main_data.json")
SUMMARY_LOG_FILE = os.path.join(LOG_FOLDER, "syslog_summary.json")

# 🛠️ Ensure directories exist
os.makedirs(LOG_FOLDER, exist_ok=True)

# ❌ Logs to be ignored
IGNORED_LOGS = ["SYS-6-LOGOUT", "SSH-5-SSH2", "SEC_LOGIN-5-LOGIN_SUCCESS", "test"]

# 🔎 Error patterns with detailed solutions and severity levels
ERROR_PATTERNS = {
    "PoE Failure": {
        "pattern": r"%ILPOWER-5-",
        "solution": "🔧 Verify PoE device compatibility and check power allocation. Inspect switch PoE settings.",
        "severity": "Warning"
    },
    "MAC Flap": {
        "pattern": r"%SW_MATM-4-MACFLAP_NOTIF",
        "solution": "🔧 Same MAC detected on multiple ports. Possible network loop or misconfigured trunking.",
        "severity": "Critical"
    },
    "Link Down": {
        "pattern": r"%LINK-3-UPDOWN",
        "solution": "🔧 Sudden interface down event. Check for cable disconnections, faulty ports, or power issues.",
        "severity": "Critical"
    },
    "Line Protocol Flap": {
        "pattern": r"%LINEPROTO-5-UPDOWN",
        "solution": "🔧 Protocol instability detected. Check VLAN assignments, spanning tree configuration, and interface duplex mismatch.",
        "severity": "Warning"
    },
    "Device Reboot": {
        "pattern": r"%SYS-5-RESTART",
        "solution": "🔧 Device has restarted. Check power sources and uptime logs.",
        "severity": "Critical"
    },
    "Device Shutdown": {
        "pattern": r"%SYS-5-SHUTDOWN",
        "solution": "🔧 Device is shutting down unexpectedly. Verify power and UPS configuration.",
        "severity": "Critical"
    },
    "STP Change": {
        "pattern": r"%SPANTREE-2-",
        "solution": "🔧 Spanning Tree Protocol (STP) change detected. Verify root bridge election and topology changes.",
        "severity": "Warning"
    },
    "Security Violation": {
        "pattern": r"%PORT_SECURITY-2-",
        "solution": "🔧 Port security violation detected. Review security policies and unauthorized MAC addresses.",
        "severity": "Critical"
    },
    "Other": {
        "pattern": r".*",
        "solution": "🔧 Further diagnosis required. Review full log details and correlate with historical incidents.",
        "severity": "Info"
    }
}

def load_json_file(file_path, default_data=None):
    """Loads a JSON file, logs errors if format is incorrect."""
    if not os.path.exists(file_path):
        print(f"🛠️ File not found, creating a new one: {file_path}")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)
        return default_data

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else default_data
    except json.JSONDecodeError as e:
        print(f"🚨 JSON Error: {file_path} is corrupted! Error: {e}")
        return default_data

def convert_utc_to_tr_time(utc_time_str):
    """Converts UTC time to Turkey (UTC+3)."""
    try:
        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M:%S UTC")
        tr_time = utc_time + timedelta(hours=3)
        return tr_time.strftime("%Y-%m-%d %H:%M:%S TR")
    except ValueError:
        return utc_time_str

def extract_interface_from_log(log_text):
    """Extracts port information from syslog message."""
    match = re.search(r"Interface (\S+)", log_text)
    return match.group(1) if match else "Device Log"

def categorize_error(log_text):
    """Analyzes the log message and assigns a category with a detailed solution and severity level."""
    for category, info in ERROR_PATTERNS.items():
        if re.search(info["pattern"], log_text):
            return category, info["solution"], info["severity"]
    return "Other", ERROR_PATTERNS["Other"]["solution"], ERROR_PATTERNS["Other"]["severity"]

def process_syslog_data():
    """Processes syslog data, summarizes, and saves the report."""
    raw_logs = load_json_file(SYSLOG_RAW_FILE, [])
    main_data = load_json_file(MAIN_DATA_FILE, [])

    if not raw_logs:
        print("⚠️ Warning: No data found in syslog_data.json!")
        return


    device_summary = defaultdict(lambda: {
        "device_id": "",
        "device_name": "",
        "total_logs": 0,
        "first_log_time": None,
        "last_log_time": None,
        "most_problematic_port": "N/A",
        "most_problematic_port_occurrences": 0,  # 🆕 En çok hata veren portun hata sayısını ayrı tutuyoruz
        "most_problematic_port_solution": "N/A",  # 🆕 Çözüm bilgisi
        "most_common_port_error_type": "N/A",
        "most_common_device_error_type": "N/A",
        "logs": {},
        "device_logs": []
    })

    port_error_counts = defaultdict(Counter)
    error_counts = defaultdict(Counter)
    device_error_counts = defaultdict(Counter)

    for log in raw_logs:
        device_id = str(log.get("deviceid"))
        log_text = log.get("text", "")
        log_time = convert_utc_to_tr_time(log.get("time", ""))

        if any(ignored in log_text for ignored in IGNORED_LOGS):
            continue

        error_category, solution, severity = categorize_error(log_text)
        interface_name = extract_interface_from_log(log_text)
        log_type = "Port Log" if interface_name != "Device Log" else "Device Log"

        # **Cihaz bilgilerini güncelle**
        device_summary[device_id]["device_id"] = device_id
        device_summary[device_id]["device_name"] = log.get("entity", "Unknown Device")
        device_summary[device_id]["total_logs"] += 1

        # **En eski ve en yeni log zamanlarını kaydet**
        if not device_summary[device_id]["first_log_time"] or log_time < device_summary[device_id]["first_log_time"]:
            device_summary[device_id]["first_log_time"] = log_time
        if not device_summary[device_id]["last_log_time"] or log_time > device_summary[device_id]["last_log_time"]:
            device_summary[device_id]["last_log_time"] = log_time

        # **Hata türlerine göre logları takip et**
        key = f"{device_id}|{interface_name}|{error_category}"
        device_summary[device_id]["logs"][key] = {
            "port": interface_name,
            "error_type": error_category,
            "log_type": log_type,
            "occurrences": error_counts[device_id][error_category] + 1,
            "severity": severity,
            "latest_log": {"timestamp": log_time, "log_text": log_text, "solution": solution}
        }

        if log_type == "Port Log":
            port_error_counts[device_id][interface_name] += 1
            error_counts[device_id][error_category] += 1
        else:
            device_error_counts[device_id][error_category] += 1

    # **Most problematic port, hata sayısı ve en büyük hatanın çözümünü belirle**
    for device_id, summary in device_summary.items():
        if summary["total_logs"] == 0:
            continue  # Eğer hiç log yoksa devam etme

        # **En çok hata alan portu bul**
        port_errors = {
            log["port"]: log["occurrences"]
            for log in summary["logs"].values()
            if log["log_type"] == "Port Log"
        }

        if port_errors:
            most_problematic_port, occurrences = max(port_errors.items(), key=lambda x: x[1])
            summary["most_problematic_port"] = most_problematic_port
            summary["most_problematic_port_occurrences"] = occurrences  # 🔥 Hata sayısını ayrı alan olarak ekledik

            # **Bu porta karşılık gelen hata ve çözümü al**
            matching_log = next(
                (log for log in summary["logs"].values() if log["port"] == most_problematic_port),
                None
            )
            if matching_log and "latest_log" in matching_log:
                summary["most_common_port_error_type"] = matching_log["error_type"]
                summary["most_problematic_port_solution"] = matching_log["latest_log"].get("solution", "No solution provided")
            else:
                summary["most_common_port_error_type"] = "No port-related errors"
                summary["most_problematic_port_solution"] = "No solution provided"

        else:
            summary["most_problematic_port"] = "No port issues detected"
            summary["most_problematic_port_occurrences"] = 0  # **Eğer sorun yoksa hata sayısı 0 olsun**
            summary["most_common_port_error_type"] = "No port-related errors"
            summary["most_problematic_port_solution"] = "No solution provided"

        # **Cihaz bazında en çok tekrar eden hatayı bul**
        device_errors = {
            log["error_type"]: log["occurrences"]
            for log in summary["logs"].values()
            if log["log_type"] == "Device Log"
        }
        if device_errors:
            most_common_device_error, occurrences = max(device_errors.items(), key=lambda x: x[1])
            summary["most_common_device_error_type"] = most_common_device_error
        else:
            summary["most_common_device_error_type"] = "No device-specific errors"

    # **Özet JSON dosyasına kaydet**
    with open(SUMMARY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(device_summary, f, indent=2, ensure_ascii=False)

    print(f"Summary log report generated: {SUMMARY_LOG_FILE}")




process_syslog_data()
