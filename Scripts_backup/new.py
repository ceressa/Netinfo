import requests
import json
import pandas as pd
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import os
import time
from functools import lru_cache
from macarna import mac_lookup

# Proxy ayarları
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# API ve dosya yolları
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_base_url = "https://network-api.npe.fedex.com/v1/device/"
input_file = "D:/INTRANET/Netinfo/Data/Statseeker_base.xlsx"
output_json_file = "D:/INTRANET/Netinfo/Data/main_data1.json"
output_excel_file = "D:/INTRANET/Netinfo/Data/main_data1.xlsx"
log_dir = "D:/INTRANET/Netinfo/Logs/New_logs/"

# Kullanıcı bilgileri
netdb_username = "3723002"
netdb_password = "Xerez386251-"

# Loglama ayarları
os.makedirs(log_dir, exist_ok=True)
log_file = f"{log_dir}main_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)


@lru_cache(maxsize=1)
def get_netdb_bearer_token():
    """
    NetDB API'den Bearer Token almak için POST isteği gönderir.
    """
    logging.info("NetDB Bearer token alınıyor...")
    auth_data = {"grant_type": "password", "username": netdb_username, "password": netdb_password}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

    try:
        response = requests.post(netdb_auth_url, data=auth_data, headers=headers, timeout=60, proxies=PROXY)
        response.raise_for_status()
        if response.status_code == 200:
            logging.info("NetDB Bearer token başarıyla alındı.")
            return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        logging.error(f"NetDB Bearer token alma hatası: {e}")
    return None


def fetch_device_data(hostname, bearer_token):
    """
    Bir cihazın verilerini NetDB API'den alır.
    """
    logging.info(f"Cihaz verileri alınıyor: {hostname}")
    urls = {
        "interfaces": f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios",
        "vlans": f"{netdb_base_url}{hostname}/vlans?device_type=cisco_ios",
        "neighbors": f"{netdb_base_url}{hostname}/neighbors?device_type=cisco_ios",
        "mac_address_table": f"{netdb_base_url}{hostname}/mac-address-table?device_type=cisco_ios"
    }
    headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}
    results = {}

    for key, url in urls.items():
        try:
            response = requests.get(url, headers=headers, timeout=60, proxies=PROXY)
            response.raise_for_status()
            results[key] = response.json().get("results", {})
            logging.info(f"{key.capitalize()} verileri başarıyla alındı: {hostname}")
        except requests.RequestException as e:
            logging.error(f"{key.capitalize()} verileri alınırken hata oluştu: {hostname}, Hata: {str(e)}")

    if len(results) == 4:
        return results
    return None

def process_vlan_data(vlan_data):
    vlan_map = {}
    for vlan in vlan_data:
        vlan_id = vlan.get('vlan_id', 'N/A')
        vlan_name = vlan.get('name', 'N/A')
        for interface in vlan.get('interfaces', []):
            # Normalize edilmiş arayüz adı ile VLAN bilgilerini ekle
            normalized_interface = normalize_interface_name(interface)
            vlan_map[normalized_interface] = {'vlan_id': vlan_id, 'vlan_name': vlan_name}
    return vlan_map


def process_mac_table(mac_table):
    processed_mac_table = {}
    for entry in mac_table:
        interface = entry.get('destination_port')
        mac_address = entry.get('destination_address')
        if interface and mac_address:
            if interface not in processed_mac_table:
                processed_mac_table[interface] = []
            vendor = mac_lookup(mac_address)
            processed_mac_table[interface].append(f"{mac_address} ({vendor})")
    return processed_mac_table


def normalize_interface_name(name):
    # Arayüz adlarını normalize et (örneğin: Gi1/0/24 -> GigabitEthernet1/0/24)
    if name.startswith("Gi"):
        return name.replace("Gi", "GigabitEthernet")
    elif name.startswith("Te"):
        return name.replace("Te", "TenGigabitEthernet")
    return name

def process_device_data(row, bearer_token):
    """
    Bir cihazın tüm verilerini işler ve yapılandırır.
    """
    hostname = row["hostname"]
    device_id = row["deviceid"]

    for attempt in range(3):
        device_data = fetch_device_data(hostname, bearer_token)
        if device_data:
            break
        logging.warning(f"Veri alınamadı: {hostname}, Deneme: {attempt + 1}")

    if not device_data:
        logging.error(f"Tüm denemeler başarısız oldu: {hostname}")
        return None

    interfaces_data = device_data.get("interfaces", {})
    vlans_data = device_data.get("vlans", [])
    neighbors_data = device_data.get("neighbors", {})
    mac_address_table = device_data.get("mac_address_table", [])

    vlan_map = process_vlan_data(vlans_data)
    processed_mac_table = process_mac_table(mac_address_table)

    port_data = []

    for interface_name, interface_details in interfaces_data.items():
        vlan_info = vlan_map.get(interface_name, {"vlan_id": "N/A", "vlan_name": "N/A"})
        neighbor_info = neighbors_data.get(interface_name, {})

        input_rate_mbps = interface_details.get("input_rate", 0) / 1_000_000
        output_rate_mbps = interface_details.get("output_rate", 0) / 1_000_000

        port_data.append({
            "deviceid": device_id,
            "hostname": hostname,
            "interface_name": interface_name,
            "description": interface_details.get("description", ""),
            "connected_macs": ", ".join(processed_mac_table.get(interface_name, [])),
            "link_status": interface_details.get("link_status", ""),
            "is_up": interface_details.get("is_up", ""),
            "protocol_status": interface_details.get("protocol_status", ""),
            "vlan_id": vlan_info["vlan_id"],
            "vlan_name": vlan_info["vlan_name"],
            "speed": interface_details.get("speed", ""),
            "duplex": interface_details.get("duplex", ""),
            "neighbor_hostname": neighbor_info.get("hostname", "N/A"),
            "neighbor_port": neighbor_info.get("remote_port", "N/A"),
            "neighbor_relation": "Üst" if neighbor_info else "Alt",
            "input_rate_mbps": round(input_rate_mbps, 2),
            "output_rate_mbps": round(output_rate_mbps, 2),
            "input_packets": interface_details.get("input_packets", ""),
            "output_packets": interface_details.get("output_packets", "")
        })

    return {hostname: {"last_updated": datetime.now().isoformat(), "ports": port_data}}


def fetch_network_data():
    """
    Tüm ağ cihazlarının verilerini toplar ve işler.
    """
    start_time = time.time()
    logging.info("Ağ veri toplama işlemi başlatılıyor...")

    df = pd.read_excel(input_file)
    switches = df[df["hostname"].str.contains("sw", case=False, na=False)]

    bearer_token = get_netdb_bearer_token()
    if not bearer_token:
        logging.error("NetDB Bearer token alınamadı. İşlem sonlandırılıyor.")
        return

    all_data = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_switch = {executor.submit(process_device_data, row, bearer_token): row for _, row in switches.iterrows()}

        for future in tqdm(as_completed(future_to_switch), total=len(switches), desc="Cihaz verileri işleniyor"):
            result = future.result()
            if result:
                all_data.update(result)

    with open(output_json_file, "w") as f:
        json.dump(all_data, f, indent=2)

    all_ports = [port for device in all_data.values() for port in device["ports"]]
    df_ports = pd.DataFrame(all_ports)
    df_ports.to_excel(output_excel_file, index=False)

    end_time = time.time()
    logging.info(f"Ağ veri toplama işlemi tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")


if __name__ == "__main__":
    fetch_network_data()
