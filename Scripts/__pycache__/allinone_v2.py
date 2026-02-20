import requests
import json
import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import io
import os
import time
from functools import lru_cache

# API ve dosya yolları
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_base_url = "https://network-api.npe.fedex.com/v1/device/"
input_file = "D:/INTRANET/Netinfo/Data/Statseeker_data.xlsx"
output_file = "D:/INTRANET/Netinfo/Data/network_device_data.json"
log_dir = "D:/INTRANET/Netinfo/Logs/New_logs/"

# Kullanıcı bilgileri
netdb_username = "3723002"
netdb_password = "Xerez386251-"

# Loglama ayarları
os.makedirs(log_dir, exist_ok=True)
log_file = f"{log_dir}new_fetch_network_data_{datetime.now().strftime('%d%m%Y%H%M')}.log"
log_handler = io.open(log_file, 'w', encoding='utf-8')
logging.basicConfig(handlers=[logging.StreamHandler(log_handler)], level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


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


def fetch_device_data(hostname, bearer_token):
    logging.info(f"Cihaz verileri alınıyor: {hostname}")
    device_url = f"{netdb_base_url}{hostname}/details?device_type=cisco_ios"
    interfaces_url = f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios"
    vlans_url = f"{netdb_base_url}{hostname}/vlans?device_type=cisco_ios"
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}

    try:
        device_response = requests.get(device_url, headers=headers, timeout=60)
        interfaces_response = requests.get(interfaces_url, headers=headers, timeout=60)
        vlans_response = requests.get(vlans_url, headers=headers, timeout=60)

        if all(response.status_code == 200 for response in [device_response, interfaces_response, vlans_response]):
            logging.info(f"Cihaz verileri başarıyla alındı: {hostname}")
            return device_response.json(), interfaces_response.json(), vlans_response.json()
        else:
            logging.error(f"Cihaz veri çekme hatası: {hostname}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Cihaz verileri alınırken hata oluştu: {hostname}, {e}")
    return None, None, None


def normalize_interface_name(name):
    return name.replace('GigabitEthernet', 'Gi').replace('TenGigabitEthernet', 'Te')


def process_device_data(row, bearer_token):
    device_id = row['deviceid']
    hostname = row['hostname']

    device_data, interfaces_data, vlans_data = fetch_device_data(hostname, bearer_token)

    if not all([device_data, interfaces_data, vlans_data]):
        logging.warning(f"Veri alınamadı: {hostname}")
        return None

    device_info = device_data.get('results', {}).get('facts', {})

    vlan_map = {}
    for vlan in vlans_data.get('results', []):
        for interface in vlan.get('interfaces', []):
            normalized_interface = normalize_interface_name(interface)
            vlan_map[normalized_interface] = {'vlan_id': vlan['vlan_id'], 'vlan_name': vlan['name']}

    port_data = []
    for interface_name, interface_details in interfaces_data.get('results', {}).items():
        normalized_name = normalize_interface_name(interface_name)
        vlan_info = vlan_map.get(normalized_name, {'vlan_id': 'N/A', 'vlan_name': 'N/A'})

        port_data.append({
            'deviceid': device_id,
            'hostname': hostname,
            'interface_name': interface_name,
            'description': interface_details.get('description', ''),
            'mac_address': interface_details.get('mac_address', ''),
            'link_status': interface_details.get('link_status', ''),
            'is_up': interface_details.get('is_up', ''),
            'protocol_status': interface_details.get('protocol_status', ''),
            'vlan_id': vlan_info['vlan_id'],
            'vlan_name': vlan_info['vlan_name']
        })

    return {hostname: {
        'device_info': {
            'serial_number': device_info.get('serial_number'),
            'model': device_info.get('model'),
            'os_version': device_info.get('os_version'),
            'uptime': device_info.get('uptime_string')
        },
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ports': port_data
    }}


def fetch_network_data():
    start_time = time.time()
    logging.info("Ağ veri toplama işlemi başlatılıyor...")

    df = pd.read_excel(input_file)
    switches = df[df['hostname'].str.contains('sw', case=False, na=False)]

    bearer_token = get_netdb_bearer_token()
    if not bearer_token:
        logging.error("NetDB Bearer token alınamadı. İşlem sonlandırılıyor.")
        return

    all_data = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_switch = {executor.submit(process_device_data, row, bearer_token): row for _, row in
                            switches.iterrows()}
        for future in tqdm(as_completed(future_to_switch), total=len(switches), desc="Cihaz verileri işleniyor"):
            result = future.result()
            if result:
                all_data.update(result)

    with open(output_file, 'w') as f:
        json.dump(all_data, f, indent=2)

    end_time = time.time()
    logging.info(f"Ağ veri toplama işlemi tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")
    logging.info(f"Veriler {output_file} dosyasına kaydedildi.")


if __name__ == "__main__":
    fetch_network_data()
