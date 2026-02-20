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
from mac_vendor_lookup import MacLookup

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
log_handler = io.open(log_file, 'w', encoding='utf-8')
logging.basicConfig(handlers=[logging.StreamHandler(log_handler)],
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    encoding='utf-8')

# MAC Vendor Lookup
mac_lookup = MacLookup()


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


def normalize_interface_name(name):
    return name.replace('GigabitEthernet', 'Gi').replace('TenGigabitEthernet', 'Te')


def get_mac_vendor(mac_address):
    try:
        return mac_lookup.lookup(mac_address)
    except KeyError:
        return "Unknown"


def fetch_device_data(hostname, bearer_token, retry=0):
    logging.info(f"Cihaz verileri alınıyor: {hostname} (Deneme {retry + 1})")
    urls = {
        'device': f"{netdb_base_url}{hostname}/details?device_type=cisco_ios",
        'interfaces': f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios",
        'vlans': f"{netdb_base_url}{hostname}/vlans?device_type=cisco_ios",
        'neighbors': f"{netdb_base_url}{hostname}/neighbors?device_type=cisco_ios"
    }
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(requests.get, url, headers=headers, timeout=60 + retry * 30): key for key, url
                         in urls.items()}
        for future in as_completed(future_to_url):
            key = future_to_url[future]
            try:
                response = future.result()
                if response.status_code == 200:
                    results[key] = response.json()
                else:
                    logging.error(f"{key.capitalize()} veri çekme hatası: {hostname}")
            except requests.exceptions.RequestException as e:
                logging.error(f"{key.capitalize()} verileri alınırken hata oluştu: {hostname}, {e}")

    if len(results) == 4:
        logging.info(f"Cihaz verileri başarıyla alındı: {hostname}")
        return results['device'], results['interfaces'], results['vlans'], results['neighbors']
    elif retry < 2:
        time.sleep(10 * (retry + 1))
        return fetch_device_data(hostname, bearer_token, retry + 1)
    else:
        return None, None, None, None


def process_device_data(row, bearer_token):
    device_id = row['deviceid']
    hostname = row['hostname']
    device_data, interfaces_data, vlans_data, neighbors_data = fetch_device_data(hostname, bearer_token)

    if not all([device_data, interfaces_data, vlans_data, neighbors_data]):
        logging.warning(f"Veri alınamadı: {hostname}")
        return {hostname: {
            'device_info': {
                'serial_number': row.get('serial', 'N/A'),
                'model': row.get('model', 'N/A'),
                'os_version': 'N/A',
                'uptime': 'N/A'
            },
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Ulaşılamadı'
        }}

    device_info = device_data.get('results', {}).get('facts', {})
    if 'stack' in device_info:
        stack_members = device_info['stack']
        device_info['serial_number'] = ','.join([member['serial_number'] for member in stack_members])

    vlan_map = {}
    vlan_info_list = []
    for vlan in vlans_data.get('results', []):
        vlan_info_list.append({
            'vlan_id': vlan['vlan_id'],
            'name': vlan['name'],
            'status': vlan['status'],
            'interface_count': len(vlan['interfaces'])
        })
        for interface in vlan.get('interfaces', []):
            normalized_interface = normalize_interface_name(interface)
            vlan_map[normalized_interface] = {'vlan_id': vlan['vlan_id'], 'vlan_name': vlan['name']}

    port_data = []
    active_gigabit_ports = 0
    for interface_name, interface_details in interfaces_data.get('results', {}).items():
        normalized_name = normalize_interface_name(interface_name)
        vlan_info = vlan_map.get(normalized_name, {'vlan_id': 'N/A', 'vlan_name': 'N/A'})

        is_gigabit = 'GigabitEthernet' in interface_name or 'TenGigabitEthernet' in interface_name
        if is_gigabit and interface_details.get('is_up'):
            active_gigabit_ports += 1

        neighbor_info = neighbors_data.get('results', {}).get(interface_name, {})
        neighbor_hostname = neighbor_info.get('hostname', 'N/A')
        neighbor_port = neighbor_info.get('remote_port', 'N/A')
        neighbor_relation = 'Üst' if neighbor_info else 'Alt'

        mac_address = interface_details.get('mac_address', '')
        mac_vendor = get_mac_vendor(mac_address) if mac_address else 'N/A'

        input_rate_mbps = interface_details.get("input_rate", 0) / 1_000_000  # Mbps
        output_rate_mbps = interface_details.get("output_rate", 0) / 1_000_000  # Mbps

        port_data.append({
            'deviceid': device_id,
            'hostname': hostname,
            'interface_name': interface_name,
            'description': interface_details.get('description', ''),
            'mac_address': mac_address,
            'mac_vendor': mac_vendor,
            'link_status': interface_details.get('link_status', ''),
            'is_up': interface_details.get('is_up', ''),
            'protocol_status': interface_details.get('protocol_status', ''),
            'vlan_id': vlan_info['vlan_id'],
            'vlan_name': vlan_info['vlan_name'],
            'speed': interface_details.get('speed', ''),
            'duplex': interface_details.get('duplex', ''),
            'neighbor_hostname': neighbor_hostname,
            'neighbor_port': neighbor_port,
            'neighbor_relation': neighbor_relation,
            'input_rate_mbps': round(input_rate_mbps, 2),
            'output_rate_mbps': round(output_rate_mbps, 2),
            'input_packets': interface_details.get('input_packets', ''),
            'output_packets': interface_details.get('output_packets', '')
        })

    return {hostname: {
        'device_info': {
            'serial_number': device_info.get('serial_number'),
            'model': device_info.get('model'),
            'os_version': device_info.get('os_version'),
            'uptime': device_info.get('uptime_string')
        },
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'active_gigabit_ports': active_gigabit_ports,
        'vlan_info': vlan_info_list,
        'ports': port_data
    }}


def fetch_network_data():
    start_time = time.time()
    logging.info("Ağ veri toplama işlemi başlatılıyor...")

    with open(input_file, 'r') as f:
        switches_data = json.load(f)
    switches = pd.DataFrame(switches_data)
    switches = switches[switches['hostname'].str.contains('sw', case=False, na=False)]

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

    network_summary = {
        'total_active_devices': sum(
            1 for device in all_data.values() if device.get('device_info', {}).get('uptime') != 'N/A'),
        'total_active_gigabit_ports': sum(device.get('active_gigabit_ports', 0) for device in all_data.values()),
        'total_devices': len(switches),
        'unreachable_devices': sum(1 for device in all_data.values() if device.get('status') == 'Ulaşılamadı')
    }
    all_data['network_summary'] = network_summary

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    end_time = time.time()
    logging.info(f"Ağ veri toplama işlemi tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")
    logging.info(f"Veriler {output_file} dosyasına kaydedildi.")


if __name__ == "__main__":
    fetch_network_data()
