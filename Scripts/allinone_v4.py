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
from dotenv import load_dotenv

load_dotenv()

# API ve dosya yolları
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_base_url = "https://network-api.npe.fedex.com/v1/device/"
input_file = "D:/INTRANET/Netinfo/Data/Statseeker_base.json"
output_file = "D:/INTRANET/Netinfo/Data/main_data.json"
log_dir = "D:/INTRANET/Netinfo/Logs/New_logs/"

# Kullanıcı bilgileri
netdb_username = os.environ.get("NETDB_USERNAME")
netdb_password = os.environ.get("NETDB_PASSWORD")

# Loglama ayarları
os.makedirs(log_dir, exist_ok=True)
log_file = f"{log_dir}main_data_{datetime.now().strftime('%d%m%Y%H%M')}.log"
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


def normalize_interface_name(name):
    return name.replace('GigabitEthernet', 'Gi').replace('TenGigabitEthernet', 'Te')


def fetch_device_data(hostname, bearer_token, retry=0):
    logging.info(f"Cihaz verileri alınıyor: {hostname} (Deneme {retry + 1})")
    device_url = f"{netdb_base_url}{hostname}/details?device_type=cisco_ios"
    interfaces_url = f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios"
    vlans_url = f"{netdb_base_url}{hostname}/vlans?device_type=cisco_ios"
    neighbors_url = f"{netdb_base_url}{hostname}/neighbors?device_type=cisco_ios"
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}

    try:
        device_response = requests.get(device_url, headers=headers, timeout=60 + retry * 30)
        interfaces_response = requests.get(interfaces_url, headers=headers, timeout=60 + retry * 30)
        vlans_response = requests.get(vlans_url, headers=headers, timeout=60 + retry * 30)
        neighbors_response = requests.get(neighbors_url, headers=headers, timeout=60 + retry * 30)

        if all(response.status_code == 200 for response in
               [device_response, interfaces_response, vlans_response, neighbors_response]):
            logging.info(f"Cihaz verileri başarıyla alındı: {hostname}")
            return device_response.json(), interfaces_response.json(), vlans_response.json(), neighbors_response.json()
        else:
            logging.error(f"Cihaz veri çekme hatası: {hostname}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Cihaz verileri alınırken hata oluştu: {hostname}, {e}")

    if retry < 2:
        time.sleep(10 * (retry + 1))
        return fetch_device_data(hostname, bearer_token, retry + 1)
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
            'vlan_name': vlan_info['vlan_name'],
            'speed': interface_details.get('speed', ''),
            'duplex': interface_details.get('duplex', ''),
            'neighbor_hostname': neighbor_hostname,
            'neighbor_port': neighbor_port,
            'neighbor_relation': neighbor_relation
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
    failed_devices = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_switch = {executor.submit(process_device_data, row, bearer_token): row for _, row in
                            switches.iterrows()}
        for future in tqdm(as_completed(future_to_switch), total=len(switches), desc="Cihaz verileri işleniyor"):
            result = future.result()
            if result:
                all_data.update(result)

    total_active_devices = sum(
        1 for device in all_data.values() if device.get('device_info', {}).get('uptime') != 'N/A')
    total_active_gigabit_ports = sum(device.get('active_gigabit_ports', 0) for device in all_data.values())

    network_summary = {
        'total_active_devices': total_active_devices,
        'total_active_gigabit_ports': total_active_gigabit_ports,
        'total_devices': len(switches),
        'unreachable_devices': len([device for device in all_data.values() if device.get('status') == 'Ulaşılamadı'])
    }

    all_data['network_summary'] = network_summary

    with open(output_file, 'w') as f:
        json.dump(all_data, f, indent=2)

    end_time = time.time()
    logging.info(f"Ağ veri toplama işlemi tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")
    logging.info(f"Veriler {output_file} dosyasına kaydedildi.")


# JSON'dan Excel'e çevirme işlevi
def convert_json_to_excel(json_file, excel_file):
    """
    JSON dosyasını Excel'e dönüştürür.
    :param json_file: JSON dosya yolu
    :param excel_file: Çıktı Excel dosya yolu
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Ports verisi
        all_ports_data = []
        device_info_data = []

        for hostname, details in data.items():
            # Device Info
            if 'device_info' in details:
                device_info = details['device_info']
                device_info_data.append({
                    'hostname': hostname,
                    'serial_number': device_info.get('serial_number', 'N/A'),
                    'model': device_info.get('model', 'N/A'),
                    'os_version': device_info.get('os_version', 'N/A'),
                    'uptime': device_info.get('uptime', 'N/A'),
                    'last_updated': details.get('last_updated', 'N/A'),
                    'active_gigabit_ports': details.get('active_gigabit_ports', 'N/A')
                })

            # Ports verisi
            if 'ports' in details:
                for port in details['ports']:
                    all_ports_data.append(port)

        # DataFrame'leri oluştur
        device_info_df = pd.DataFrame(device_info_data)
        ports_df = pd.DataFrame(all_ports_data)

        # Excel'e yaz
        with pd.ExcelWriter(excel_file) as writer:
            device_info_df.to_excel(writer, sheet_name='Device Info', index=False)
            ports_df.to_excel(writer, sheet_name='Ports', index=False)

        logging.info(f"JSON dosyası Excel'e dönüştürüldü: {excel_file}")
    except Exception as e:
        logging.error(f"JSON'dan Excel'e dönüştürme sırasında hata oluştu: {e}")

# Statseeker_base dosyasını Excel'e çevirme
def convert_statseeker_to_excel(json_file, excel_file):
    """
    Statseeker_base.json dosyasını Excel'e dönüştürür.
    :param json_file: JSON dosya yolu
    :param excel_file: Çıktı Excel dosya yolu
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Tüm veriyi DataFrame'e çevir
        df = pd.DataFrame(data)

        # Excel'e yaz
        df.to_excel(excel_file, index=False)
        logging.info(f"Statseeker_base.json dosyası Excel'e dönüştürüldü: {excel_file}")
    except Exception as e:
        logging.error(f"Statseeker_base.json'dan Excel'e dönüştürme sırasında hata oluştu: {e}")

# Ana fonksiyon
if __name__ == "__main__":
    # main_data.json dosyasını dönüştür
    convert_json_to_excel(
        json_file="D:/INTRANET/Netinfo/Data/main_data.json",
        excel_file="D:/INTRANET/Netinfo/Data/main_data.xlsx"
    )

    # Statseeker_base.json dosyasını dönüştür
    convert_statseeker_to_excel(
        json_file="D:/INTRANET/Netinfo/Data/Statseeker_base.json",
        excel_file="D:/INTRANET/Netinfo/Data/Statseeker_base.xlsx"
    )
