import requests
import pandas as pd
from datetime import datetime
import pytz
import json
import urllib3
import os
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Proxy settings
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# API connection details
base_url = 'https://statseeker.emea.fedex.com/api/v2.1/'
user = 'tr-api'
password = 'F3xpres!'

fields = {
    'device': 'id,deviceid,hostname,ipaddress,ping_state',
    'inventory': 'id,deviceid,serial,model'
}

# URLs
urls = {
    name: f"{base_url}cdt_{name}?fields={fields[name]}&groups=NOC-Turkey&links=none&limit=10000"
    for name in fields
}

# Log settings
log_directory = "D:/INTRANET/Netinfo/Logs/Latest_Logs"
os.makedirs(log_directory, exist_ok=True)

log_start_date = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y%m%d')
log_file_path = os.path.join(log_directory, f"Statseeker_base_{log_start_date}.log")

def log_message(message):
    """Write log messages to a file."""
    global log_start_date
    current_date = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y%m%d')

    if current_date != log_start_date:
        log_start_date = current_date
        global log_file_path
        log_file_path = os.path.join(log_directory, f"Statseeker_base_{current_date}.log")

    timestamp = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"{timestamp} - {message}\n")

def fetch_data(url):
    """Fetch data from API."""
    try:
        response = requests.get(url, auth=(user, password), verify=False, timeout=60)
        if response.status_code == 200:
            log_message(f"Data fetched successfully from {url}")
            return response.json()
        else:
            log_message(f"Error {response.status_code} fetching data from {url}")
    except requests.exceptions.RequestException as e:
        log_message(f"Error fetching data from {url}: {e}")
    return None

def process_data(data):
    """Convert JSON data to Pandas DataFrame."""
    if 'data' in data and 'objects' in data['data']:
        objects = data['data']['objects']
        if objects and isinstance(objects, list) and 'data' in objects[0]:
            return pd.DataFrame(objects[0]['data'])
    log_message("Unexpected data structure")
    return pd.DataFrame()

def determine_device_type(model):
    """Determine the device type based on the model."""
    if not isinstance(model, str):  # Modelin string olup olmadığını kontrol et
        return "Unknown"

    SWITCH_MODELS = ["C9300", "WS-C2960X", "WS-C3850", "C9500", "C9300L"]
    ROUTER_MODELS = ["ISR4351", "ISR4451"]

    if any(sw in model for sw in SWITCH_MODELS):
        return "Switch"
    elif any(rt in model for rt in ROUTER_MODELS):
        return "Router"
    return "Unknown"


def load_previous_data():
    """Load previous cycle's device data."""
    previous_data_file = 'D:/INTRANET/Netinfo/Data/statseeker_base_previous.json'
    if os.path.exists(previous_data_file):
        with open(previous_data_file, 'r') as f:
            try:
                return {d['deviceid']: d for d in json.load(f)}
            except json.JSONDecodeError:
                return {}
    return {}

def update_status_change(device, previous_data):
    """Update device status change based on previous cycle."""
    deviceid = device['deviceid']
    current_is_up = 1 if device['ping_state'] == 'up' else 0

    if device['ping_state'] == 'unknown':
        return None  # "unknown" olanları ignore ediyoruz

    previous_is_up = previous_data.get(deviceid, {}).get('is_up', current_is_up)
    last_change_time = previous_data.get(deviceid, {}).get('last_status_change', None)

    if current_is_up != previous_is_up:
        last_change_time = datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%Y-%m-%d %H:%M:%S')

    device['previous_is_up'] = previous_is_up
    device['last_status_change'] = last_change_time

    return device

def extract_location(hostname):
    """Extract location from hostname."""
    match = re.search(r'Tr([A-Za-z0-9]+?)(?=csw|sw|ttr)', hostname, re.IGNORECASE)
    return match.group(1) if match else 'Unknown'

def update_data():
    """Fetch and process data, updating status change information."""
    previous_data = load_previous_data()
    data_frames = {}

    for name, url in urls.items():
        log_message(f"Fetching {name} data...")
        data = fetch_data(url)
        if data:
            df = process_data(data)
            data_frames[name] = df
            log_message(f"{name} data fetched with {len(df)} rows.")
        else:
            log_message(f"Failed to fetch {name} data.")

    if 'device' in data_frames and 'inventory' in data_frames:
        merged_data = data_frames['device'].merge(data_frames['inventory'], on='deviceid', how='left')
        merged_data = merged_data.rename(columns={'id_x': 'id'})
        merged_data = merged_data.drop(columns=[col for col in ['id_y'] if col in merged_data.columns])
        merged_data['device_type'] = merged_data['model'].apply(determine_device_type)
        merged_data = merged_data[merged_data['device_type'] != 'Unknown']
        merged_data = merged_data[merged_data['hostname'].str.contains(r'(sw|tt)', case=False, na=False)]

        # Ping_state durumlarını numerik hale çevir
        merged_data['ping_state'] = merged_data['ping_state'].apply(lambda x: x.lower() if isinstance(x, str) else 'unknown')
        merged_data = merged_data[merged_data['ping_state'] != 'unknown']  # "unknown" olanları at
        merged_data['ping_state_numeric'] = merged_data['ping_state'].map({'up': 1, 'down': 0})

        # Lokasyon bilgisini ekle
        merged_data['location'] = merged_data['hostname'].apply(extract_location)
        merged_data['city'] = "Istanbul"  # Sabit değer

        # Cihaz durumu değişim bilgilerini ekle
        current_data = [update_status_change(device, previous_data) for device in merged_data.to_dict(orient='records')]
        current_data = [d for d in current_data if d is not None]  # None olanları at

        # Güncellenmiş JSON dosyalarını kaydet
        json_file = 'D:/INTRANET/Netinfo/Data/statseeker_base.json'
        with open(json_file, 'w') as f:
            json.dump(current_data, f, indent=2)

        previous_data_file = 'D:/INTRANET/Netinfo/Data/statseeker_base_previous.json'
        with open(previous_data_file, 'w') as f:
            json.dump(current_data, f, indent=2)

        log_message(f"Data saved to {json_file}")

    log_message("Update complete.")

if __name__ == "__main__":
    update_data()
