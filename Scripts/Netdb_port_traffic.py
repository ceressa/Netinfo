import requests
import json
import logging
from datetime import datetime
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

# API ve dosya yolları
API_AUTH_URL = "https://network-api.npe.fedex.com/v1/authorize"
DEVICE_INTERFACES_URL_TEMPLATE = "https://network-api.npe.fedex.com/v1/device/{hostname}/interfaces?device_type=cisco_ios"
OUTPUT_JSON_FILE = "filtered_switch_interfaces.json"
OUTPUT_EXCEL_FILE = "filtered_switch_interfaces.xlsx"

# Kullanıcı bilgileri
USERNAME = os.environ.get("NETDB_USERNAME")
PASSWORD = os.environ.get("NETDB_PASSWORD")

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_bearer_token():
    """NetDB Bearer token alır."""
    logging.info("Bearer token alınıyor...")
    auth_data = {'grant_type': 'password', 'username': USERNAME, 'password': PASSWORD}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
    try:
        response = requests.post(API_AUTH_URL, data=auth_data, headers=headers, timeout=10)
        response.raise_for_status()
        logging.info("Bearer token başarıyla alındı.")
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        logging.error(f"Bearer token alma hatası: {e}")
        return None

def get_device_interfaces(hostname, token):
    """Cihaz arayüz verilerini alır."""
    url = DEVICE_INTERFACES_URL_TEMPLATE.format(hostname=hostname)
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        logging.info(f"{hostname} arayüz verileri başarıyla alındı.")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"{hostname} arayüz verileri alınamadı: {e}")
        return None

def filter_active_ports(interface_data):
    """`is_up = True` olan portları filtreler."""
    active_ports = []
    for interface_name, details in interface_data.get("results", {}).items():
        if details.get("is_up", False):
            active_ports.append({
                "Interface Name": interface_name,
                "Description": details.get("description", ""),
                "MAC Address": details.get("mac_address", ""),
                "Link Status": details.get("link_status", ""),
                "Protocol Status": details.get("protocol_status", ""),
                "Bandwidth": details.get("bandwidth", ""),
                "Input Rate": details.get("input_rate", ""),
                "Output Rate": details.get("output_rate", ""),
                "Input Packets": details.get("input_packets", ""),
                "Output Packets": details.get("output_packets", "")
            })
    logging.info(f"Aktif port sayısı: {len(active_ports)}")
    return active_ports

def save_results_to_files(data, json_file, excel_file):
    """Sonuçları JSON ve Excel dosyasına kaydeder."""
    try:
        with open(json_file, "w") as f:
            json.dump(data, f, indent=2)
        logging.info(f"Veri JSON dosyasına kaydedildi: {json_file}")

        df = pd.DataFrame(data["ports"])
        df.to_excel(excel_file, index=False)
        logging.info(f"Veri Excel dosyasına kaydedildi: {excel_file}")
    except Exception as e:
        logging.error(f"Veriler kaydedilirken hata oluştu: {e}")

def main():
    """Ana işlem."""
    logging.info("İşlem başlatılıyor...")
    token = get_bearer_token()
    if not token:
        logging.error("Bearer token alınamadı, işlem sonlandırılıyor.")
        return

    hostname = "TrCHO1104sw06"  # Test edilen hostname
    interface_data = get_device_interfaces(hostname, token)
    if not interface_data:
        logging.error(f"{hostname} için veri alınamadı, işlem sonlandırılıyor.")
        return

    active_ports = filter_active_ports(interface_data)
    result_data = {
        "hostname": hostname,
        "last_updated": datetime.now().isoformat(),
        "ports": active_ports
    }

    save_results_to_files(result_data, OUTPUT_JSON_FILE, OUTPUT_EXCEL_FILE)
    logging.info("İşlem tamamlandı.")

if __name__ == "__main__":
    main()
