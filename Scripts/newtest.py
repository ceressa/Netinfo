import requests
import json
import logging
from datetime import datetime
from mac_vendor_lookup import MacLookup, VendorNotFoundError
from functools import lru_cache
import re
import time
import os
from dotenv import load_dotenv

load_dotenv()

# API ve dosya yolları
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_base_url = "https://network-api.npe.fedex.com/v1/device/"
output_file = "D:/INTRANET/Netinfo/Data/traytsw01_data.json"

# Kullanıcı bilgileri
netdb_username = os.environ.get("NETDB_USERNAME")
netdb_password = os.environ.get("NETDB_PASSWORD")

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def normalize_port_name(port_name):
    """Normalize port names to a consistent format."""
    if port_name.startswith("Gi"):
        return port_name.replace("Gi", "GigabitEthernet")
    return port_name

def fetch_with_retries(url, headers, retries=3):
    """Fetch data with retries."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Attempt {attempt} failed for {url}: {e}")
            if attempt == retries:
                logging.error(f"Max retries reached for {url}")
                return None
            time.sleep(2 ** attempt)  # Exponential backoff

def fetch_device_data(hostname, bearer_token):
    logging.info(f"Cihaz verileri alınıyor: {hostname}")
    urls = {
        'device': f"{netdb_base_url}{hostname}/details?device_type=cisco_ios",
        'interfaces': f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios",
        'vlans': f"{netdb_base_url}{hostname}/vlans?device_type=cisco_ios",
        'neighbors': f"{netdb_base_url}{hostname}/neighbors?device_type=cisco_ios",
        'mac_address_table': f"{netdb_base_url}{hostname}/mac-address-table?device_type=cisco_ios"
    }
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}

    results = {}
    for key, url in urls.items():
        results[key] = fetch_with_retries(url, headers)

    return results

def process_device_data(hostname, data):
    device_info = data['device'].get('results', {}).get('facts', {}) if data['device'] else {}
    interfaces_data = data['interfaces'].get('results', {}) if data['interfaces'] else {}
    vlans_data = data['vlans'].get('results', []) if data['vlans'] else []
    neighbors_data = data['neighbors'].get('results', {}) if data['neighbors'] else {}
    mac_address_table = data['mac_address_table'].get('results', []) if data['mac_address_table'] else []

    port_to_vlan_map = {}
    for vlan in vlans_data:
        for interface in vlan.get('interfaces', []):
            normalized_interface = normalize_port_name(interface)
            port_to_vlan_map.setdefault(normalized_interface, []).append({
                'vlan_id': vlan['vlan_id'],
                'vlan_name': vlan['name'],
                'status': vlan['status']
            })

    port_data = []

    # MAC adreslerini filtrele ve vendor bilgilerini al
    mac_map = {}
    for entry in mac_address_table:
        port_name = normalize_port_name(entry['destination_port'])
        if port_name.startswith("GigabitEthernet"):
            mac_address = entry['destination_address']
            for attempt in range(1, 4):
                try:
                    vendor = mac_lookup.lookup(mac_address) if mac_address else "Unknown"
                    break
                except VendorNotFoundError:
                    logging.warning(f"Vendor not found for MAC: {mac_address} on attempt {attempt}")
                    if attempt == 3:
                        vendor = "Unknown"
            if port_name not in mac_map:
                mac_map[port_name] = []
            mac_map[port_name].append(f"{mac_address} ({vendor})")

    for interface_name, interface_details in interfaces_data.items():
        normalized_interface = normalize_port_name(interface_name)
        vlans_info = port_to_vlan_map.get(normalized_interface, [{'vlan_id': 'N/A', 'vlan_name': 'N/A', 'status': 'N/A'}])
        neighbor_info = neighbors_data.get(normalized_interface, {})

        connected_macs = mac_map.get(normalized_interface, [])

        input_rate_mbps = interface_details.get("input_rate", 0) / 1_000_000  # Mbps
        output_rate_mbps = interface_details.get("output_rate", 0) / 1_000_000  # Mbps

        port_data.append({
            'deviceid': device_info.get('device_id', 'N/A'),
            'hostname': hostname,
            'interface_name': normalized_interface,
            'description': interface_details.get('description', ''),
            'connected_macs': ', '.join(connected_macs),
            'link_status': interface_details.get('link_status', ''),
            'is_up': interface_details.get('is_up', False),
            'protocol_status': interface_details.get('protocol_status', ''),
            'vlans': vlans_info,
            'speed': interface_details.get('speed', ''),
            'duplex': interface_details.get('duplex', ''),
            'neighbor_hostname': neighbor_info.get('hostname', 'N/A'),
            'neighbor_port': neighbor_info.get('remote_port', 'N/A'),
            'neighbor_relation': 'Üst' if neighbor_info else 'Alt',
            'input_rate_mbps': round(input_rate_mbps, 2),
            'output_rate_mbps': round(output_rate_mbps, 2),
            'input_packets': interface_details.get('input_packets', 0),
            'output_packets': interface_details.get('output_packets', 0)
        })

    return {
        'device_info': device_info,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ports': port_data
    }

def main():
    hostname = "TrASR1117sw01"  # Cihaz adı burada güncellendi.
    bearer_token = get_netdb_bearer_token()
    if not bearer_token:
        logging.error("NetDB Bearer token alınamadı. İşlem sonlandırılıyor.")
        return

    device_data = fetch_device_data(hostname, bearer_token)
    if not device_data:
        logging.error(f"Veri alınamadı: {hostname}")
        return

    processed_data = process_device_data(hostname, device_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2, ensure_ascii=False)

    logging.info(f"Veriler {output_file} dosyasına kaydedildi.")

if __name__ == "__main__":
    main()
