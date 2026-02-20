import requests
import json
import pandas as pd
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from mac_vendor_lookup import MacLookup
import os
from dotenv import load_dotenv

load_dotenv()

# API ve dosya yolları
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_base_url = "https://network-api.npe.fedex.com/v1/device/"
input_file = "D:/INTRANET/Netinfo/Data/Statseeker_base.xlsx"
output_json_file = "D:/INTRANET/Netinfo/Data/Netdb_port_data_v2.json"
output_excel_file = "D:/INTRANET/Netinfo/Data/Netdb_port_data_v2.xlsx"
log_file = "D:/INTRANET/Netinfo/Logs/switch_data.log"

# Kullanıcı bilgileri
netdb_username = os.environ.get("NETDB_USERNAME")
netdb_password = os.environ.get("NETDB_PASSWORD")

# Loglama ayarları
logging.basicConfig(filename=log_file, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# MAC Vendor Lookup
mac_lookup = MacLookup()

# Bearer token alma fonksiyonu
def get_netdb_bearer_token():
    logging.info("NetDB Bearer token alınıyor...")
    auth_data = {'grant_type': 'password', 'username': netdb_username, 'password': netdb_password}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
    try:
        response = requests.post(netdb_auth_url, data=auth_data, headers=headers, timeout=30)
        response.raise_for_status()
        logging.info("NetDB Bearer token başarıyla alındı.")
        return response.json().get('access_token')
    except requests.RequestException as e:
        logging.error(f"NetDB Bearer token alma hatası: {e}")
    return None

# MAC adres tablosunu çekme
def get_mac_address_table(hostname, bearer_token):
    url = f"{netdb_base_url}{hostname}/mac-address-table?device_type=cisco_ios"
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        logging.info(f"MAC adres tablosu başarıyla alındı: {hostname}")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"MAC adres tablosu alınırken hata oluştu: {e}")
    return None

# Cihaz verilerini çekme
def get_device_data(hostname, bearer_token):
    logging.info(f"Cihaz verileri alınıyor: {hostname}")
    interfaces_url = f"{netdb_base_url}{hostname}/interfaces?device_type=cisco_ios"
    headers = {'Authorization': f'Bearer {bearer_token}', 'Accept': 'application/json'}

    try:
        response = requests.get(interfaces_url, headers=headers, timeout=30)
        response.raise_for_status()
        logging.info(f"Cihaz verileri başarıyla alındı: {hostname}")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Cihaz verileri alınırken hata oluştu: {e}")
    return None

# MAC adres tablosunu işleme
def process_mac_table(mac_table):
    processed_mac_table = {}
    for entry in mac_table.get('results', []):
        mac_vendor = "Unknown"
        mac_address = entry.get('destination_address', "")
        if mac_address:
            try:
                mac_vendor = mac_lookup.lookup(mac_address)
            except Exception as e:
                logging.warning(f"MAC adresi için vendor bulunamadı: {mac_address}, Hata: {e}")

        port = entry.get('destination_port', "")
        if port not in processed_mac_table:
            processed_mac_table[port] = []
        processed_mac_table[port].append(f"{mac_address} ({mac_vendor})")
    return processed_mac_table

# Port verilerini işleme
def filter_active_ports(interface_data, mac_table, hostname):
    active_ports = []
    for interface_name, details in interface_data.get("results", {}).items():
        if details.get("is_up", False):
            input_rate_mbps = details.get("input_rate", 0) / 1_000_000  # Mbps
            output_rate_mbps = details.get("output_rate", 0) / 1_000_000  # Mbps

            mac_info = ", ".join(mac_table.get(interface_name, []))

            active_ports.append({
                "Hostname": hostname,
                "Interface Name": interface_name,
                "Description": details.get("description", ""),
                "Link Status": details.get("link_status", ""),
                "Protocol Status": details.get("protocol_status", ""),
                "Bandwidth": details.get("bandwidth", ""),
                "Input Rate (Mbps)": round(input_rate_mbps, 2),
                "Output Rate (Mbps)": round(output_rate_mbps, 2),
                "Input Packets": details.get("input_packets", ""),
                "Output Packets": details.get("output_packets", ""),
                "Connected MACs": mac_info
            })
    return active_ports

# Cihaz verilerini işleme
def process_device_data(row, bearer_token):
    hostname = row['hostname']

    # Arayüz verilerini al
    interface_data = get_device_data(hostname, bearer_token)
    if not interface_data:
        logging.warning(f"Veri alınamadı: {hostname}")
        return None

    # MAC adres tablosunu al
    mac_table = get_mac_address_table(hostname, bearer_token)
    if not mac_table:
        logging.warning(f"MAC adres tablosu alınamadı: {hostname}")
        mac_table = {}

    processed_mac_table = process_mac_table(mac_table)
    active_ports = filter_active_ports(interface_data, processed_mac_table, hostname)

    return {
        hostname: {
            "last_updated": datetime.now().isoformat(),
            "ports": active_ports
        }
    }

# Sonuçları kaydetme
def save_results_to_files(data, json_file, excel_file):
    # JSON olarak kaydet
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    logging.info(f"Veri JSON dosyasına kaydedildi: {json_file}")

    # Excel olarak kaydet
    all_ports = []
    for hostname, device_data in data.items():
        for port in device_data["ports"]:
            all_ports.append(port)

    df = pd.DataFrame(all_ports)
    df.to_excel(excel_file, index=False)
    logging.info(f"Veri Excel dosyasına kaydedildi: {excel_file}")

# Ana işlem
def main():
    start_time = time.time()
    logging.info("Veri toplama işlemi başlatılıyor...")

    # Giriş dosyasından hostname'leri okuma
    df = pd.read_excel(input_file)
    switches = df[df['hostname'].str.contains('sw', case=False, na=False)]

    # Bearer token alma
    bearer_token = get_netdb_bearer_token()
    if not bearer_token:
        logging.error("NetDB Bearer token alınamadı. İşlem sonlandırılıyor.")
        return

    # Tüm cihazların verilerini toplama
    all_data = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_switch = {executor.submit(process_device_data, row, bearer_token): row for _, row in
                            switches.iterrows()}
        for future in tqdm(as_completed(future_to_switch), total=len(switches), desc="Cihaz verileri işleniyor"):
            result = future.result()
            if result:
                all_data.update(result)

    # Sonuçları JSON ve Excel olarak kaydetme
    save_results_to_files(all_data, output_json_file, output_excel_file)

    end_time = time.time()
    logging.info(f"İşlem tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")

if __name__ == "__main__":
    main()
