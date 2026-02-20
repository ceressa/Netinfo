import requests
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import os
from functools import lru_cache
import time
from cryptography.fernet import Fernet

# File paths
CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"
LOG_DIR = "D:/INTRANET/Netinfo/Logs/Latest_Logs"

# API and input/output paths
NETDB_AUTH_URL = "https://network-api.npe.fedex.com/v1/authorize"
NETDB_BASE_URL = "https://network-api.npe.fedex.com/v1/device/"
INPUT_FILE = "D:/INTRANET/Netinfo/Data/network_device_inventory.json"
OUTPUT_JSON_FILE = "D:/INTRANET/Netinfo/Data/main_router_data.json"
OUTPUT_EXCEL_FILE = "D:/INTRANET/Netinfo/Data/main_router_data.xlsx"

# Proxy settings
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# Router models
ROUTER_MODELS = ["ISR4351", "ISR4451", "8300"]

# Logging setup
os.makedirs(LOG_DIR, exist_ok=True)
log_file_date = datetime.now().strftime('%Y%m%d')
log_file = os.path.join(LOG_DIR, f"router_ports_{log_file_date}.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    encoding="utf-8"
)

def log_message(level, message):
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)

# Load encryption key
def load_key():
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("Secret key file not found.")
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()

ENCRYPTION_KEY = load_key()

# Encryption and decryption
def decrypt_data(encrypted_data):
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_data.encode()).decode()

# Load credentials
def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("Credentials file not found.")
    with open(CREDENTIALS_FILE, 'r') as f:
        credentials = json.load(f)
    return credentials

@lru_cache(maxsize=1)
def get_netdb_credentials():
    credentials = load_credentials()
    username = credentials["netdb"]["username"]
    password = decrypt_data(credentials["netdb"]["password"])
    return username, password

@lru_cache(maxsize=1)
def get_netdb_bearer_token():
    username, password = get_netdb_credentials()
    auth_data = {"grant_type": "password", "username": username, "password": password}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

    for attempt in range(3):
        try:
            response = requests.post(NETDB_AUTH_URL, data=auth_data, headers=headers, timeout=60)
            response.raise_for_status()
            token = response.json().get("access_token")
            if token:
                log_message("info", "Token successfully retrieved.")
                return token
            else:
                log_message("error", "Failed to retrieve token.")
        except requests.RequestException as e:
            log_message("error", f"Error retrieving token: {e}")
    raise RuntimeError("Failed to obtain bearer token after multiple attempts.")

# Fetch device data with retry logic
def fetch_device_data(hostname, bearer_token, max_retries=3):
    """
    Fetch device data for the given hostname with retry logic.
    """
    log_message("info", f"Fetching device data for: {hostname}")
    urls = {
        "interfaces": f"{NETDB_BASE_URL}{hostname}/interfaces?device_type=cisco_ios",
        "neighbors": f"{NETDB_BASE_URL}{hostname}/neighbors?device_type=cisco_ios",
    }
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}
    results = {}

    for key, url in urls.items():
        for attempt in range(max_retries):
            try:
                log_message("info", f"Attempt {attempt + 1} for {key} data: {url}")
                response = requests.get(url, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
                results[key] = response.json().get('results', {})
                break  # Break out of the retry loop on success
            except requests.RequestException as e:
                log_message("error", f"Error fetching {key} for {hostname} (Attempt {attempt + 1}): {e}")
                if attempt + 1 == max_retries:
                    log_message("warning", f"Max retries reached for {key} of {hostname}. Skipping...")
    return results if len(results) == len(urls) else None


# Process data
def process_device_data(row, bearer_token):
    hostname = row['hostname']
    deviceid = row.get('deviceid', 'N/A')
    log_message("info", f"Processing device: {hostname} (Device ID: {deviceid})")

    device_data = fetch_device_data(hostname, bearer_token)
    if not device_data:
        log_message("warning", f"Failed to fetch data for: {hostname}")
        return None

    interfaces_data = device_data.get('interfaces', {})
    neighbors_data = device_data.get('neighbors', {})
    port_data = [
        {
            'hostname': hostname,
            'deviceid': deviceid,
            'interface_name': interface_name,
            'description': details.get('description', ''),
            'link_status': details.get('link_status', 'N/A'),
            'neighbor_hostname': neighbors_data.get(interface_name, {}).get('hostname', 'N/A'),
            'neighbor_port': neighbors_data.get(interface_name, {}).get('remote_port', 'N/A'),
        }
        for interface_name, details in interfaces_data.items()
    ]
    return {'hostname': hostname, 'deviceid': deviceid, 'ports': port_data}

# Fetch all network data
def fetch_network_data():
    log_message("info", "Starting network data fetch.")

    # JSON'dan veriyi oku
    data = read_json_file(INPUT_FILE)

    # Router modellerine göre filtreleme
    df_routers = [device for device in data if any(rt in device.get('model', '') for rt in ROUTER_MODELS)]

    bearer_token = get_netdb_bearer_token()
    all_data = []
    failed_devices = []  # Datası alınamayan cihazları tutacak liste

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_device = {
            executor.submit(process_device_data, row, bearer_token): row
            for row in df_routers
        }
        for future in tqdm(as_completed(future_to_device), total=len(future_to_device), desc="Processing devices"):
            try:
                result = future.result()
                if result:
                    all_data.append(result)
                else:
                    failed_devices.append(future_to_device[future]['hostname'])  # Başarısız cihazları ekle
            except Exception as e:
                row = future_to_device[future]
                failed_devices.append(row['hostname'])
                log_message("error", f"Error processing device {row['hostname']}: {e}")

    # Çalışma sonunda alınamayan cihazları logla
    if failed_devices:
        log_message("warning", f"Data fetch failed for the following devices: {', '.join(failed_devices)}")
    else:
        log_message("info", "All device data fetched successfully.")

    # Sonuçları dosyalara yaz
    with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2)

    # Excel yerine JSON çıktısını güncelledik
    log_message("info", "Network data fetch complete.")

# JSON'dan veri okuma
def read_json_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input JSON file not found: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

if __name__ == "__main__":
    fetch_network_data()
