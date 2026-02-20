import requests
import json
import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from macarna import mac_lookup
from functools import lru_cache
import time
import io
import os

# API ve dosya yolları
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_base_url = "https://network-api.npe.fedex.com/v1/device/"
input_file = "D:/INTRANET/Netinfo/Data/Statseeker_base.json"
output_file = "D:/INTRANET/Netinfo/Data/main_data.json"
log_dir = "D:/INTRANET/Netinfo/Logs/New_logs/"

# Kullanıcı bilgileri
netdb_username = "3723002"
netdb_password = "Xerez386251-"

# Loglama ayarları
os.makedirs(log_dir, exist_ok=True)
log_file = f"{log_dir}main_data_{datetime.now().strftime('%d%m%Y%H%M')}.log"
logging.basicConfig(
    handlers=[logging.FileHandler(log_file, encoding='utf-8')],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@lru_cache(maxsize=1)
def get_netdb_bearer_token():
    logging.info("NetDB Bearer token alınıyor...")
    auth_data = {'grant_type': 'password', 'username': netdb_username, 'password': netdb_password}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
    try:
        response = requests.post(netdb_auth_url, data=auth_data, headers=headers, timeout=60)
        if response.status_code == 200:
            logging.info("NetDB Bearer token başarıyla alındı.")
            return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        logging.error(f"NetDB Bearer token alma hatası: {e}")
    return None

def get_mac_vendor(mac_address):
    try:
        return mac_lookup(mac_address)
    except ValueError:
        return "Unknown Vendor"

def process_mac_table(mac_table):
    processed_mac_table = {}
    for entry in mac_table.get('results', []):
        mac_address = entry.get('destination_address', "")
        port = entry.get('destination_port', "")
        if not mac_address or not port:
            continue
        vendor = get_mac_vendor(mac_address)
        processed_mac_table.setdefault(port, []).append(f"{mac_address} ({vendor})")
    return processed_mac_table

def fetch_device_data(hostname, bearer_token, retry=0):
    logging.info(f"Cihaz verileri alınıyor: {hostname} (Deneme {retry + 1})")
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}
    urls = {
        'device': f"{netdb_base_url}{hostname}/details?device_type=cisco_ios",
        'interfaces': f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios",
        'vlans': f"{netdb_base_url}{hostname}/vlans?device_type=cisco_ios",
        'neighbors': f"{netdb_base_url}{hostname}/neighbors?device_type=cisco_ios",
        'mac_address_table': f"{netdb_base_url}{hostname}/mac-address-table?device_type=cisco_ios"
    }
    try:
        responses = {key: requests.get(url, headers=headers, timeout=60) for key, url in urls.items()}
        if all(response.status_code == 200 for response in responses.values()):
            logging.info(f"Cihaz verileri başarıyla alındı: {hostname}")
            return {key: response.json() for key, response in responses.items()}
        else:
            logging.error(f"Cihaz veri çekme hatası: {hostname}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Cihaz verileri alınırken hata oluştu: {hostname}, {e}")
    if retry < 2:
        time.sleep(10 * (retry + 1))
        return fetch_device_data(hostname, bearer_token, retry + 1)
    return None


def process_device_data(row, bearer_token):
    hostname = row['hostname']
    device_data = fetch_device_data(hostname, bearer_token)
    if not device_data:
        logging.warning(f"Veri alınamadı: {hostname}")
        return {hostname: {'status': 'Ulaşılamadı', 'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}

    interfaces_data = device_data['interfaces'].get('results', {})
    mac_address_table = device_data['mac_address_table'].get('results', [])

    processed_mac_table = process_mac_table({'results': mac_address_table})

    port_data = []
    for interface_name, interface_details in interfaces_data.items():
        mac_info = ", ".join(processed_mac_table.get(interface_name, []))
        port_data.append({
            'deviceid': row['deviceid'],
            'hostname': hostname,
            'interface_name': interface_name,
            'description': interface_details.get('description', ''),
            'connected_macs': mac_info,
            'link_status': interface_details.get('link_status', ''),
            'is_up': interface_details.get('is_up', ''),
            'protocol_status': interface_details.get('protocol_status', ''),
            'vlan_id': interface_details.get('vlan_id', 'N/A'),
            'vlan_name': interface_details.get('vlan_name', 'N/A'),
            'speed': interface_details.get('speed', ''),
            'duplex': interface_details.get('duplex', ''),
            'neighbor_hostname': interface_details.get('neighbor_hostname', 'N/A'),
            'neighbor_port': interface_details.get('neighbor_port', 'N/A'),
            'neighbor_relation': interface_details.get('neighbor_relation', 'N/A'),
            'input_rate_mbps': round(interface_details.get('input_rate', 0) / 1_000_000, 2),
            'output_rate_mbps': round(interface_details.get('output_rate', 0) / 1_000_000, 2),
            'input_packets': interface_details.get('input_packets', ''),
            'output_packets': interface_details.get('output_packets', '')
        })

    return {hostname: {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ports': port_data
    }}

def fetch_network_data():
    start_time = time.time()
    logging.info("Ağ veri toplama işlemi başlatılıyor...")

    with open(input_file, 'r') as f:
        switches_data = json.load(f)
    switches = pd.DataFrame(switches_data)

    bearer_token = get_netdb_bearer_token()
    if not bearer_token:
        logging.error("NetDB Bearer token alınamadı. İşlem sonlandırılıyor.")
        return

    all_data = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_switch = {executor.submit(process_device_data, row, bearer_token): row for _, row in switches.iterrows()}
        for future in tqdm(as_completed(future_to_switch), total=len(switches), desc="Cihaz verileri işleniyor"):
            result = future.result()
            if result:
                all_data.update(result)

    with open(output_file, 'w') as f:
        json.dump(all_data, f, indent=2)

    end_time = time.time()
    logging.info(f"Ağ veri toplama işlemi tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")

if __name__ == "__main__":
    fetch_network_data()
