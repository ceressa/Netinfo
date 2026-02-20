import requests
import json
import logging
from datetime import datetime
import pandas as pd

# API ve dosya yollari
api_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
device_interfaces_url_template = "https://network-api.npe.fedex.com/v1/device/{hostname}/interfaces?device_type=cisco_ios"
output_json_file = "main_data.json"
output_excel_file = "main_data.xlsx"

# Kullanici bilgileri
username = "3723002"
password = "Xerez386251-"

# Loglama ayarlari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Bearer token alma fonksiyonu
def get_bearer_token():
    logging.info("NetDB Bearer token aliniyor...")
    auth_data = {'grant_type': 'password', 'username': username, 'password': password}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
    try:
        response = requests.post(api_auth_url, data=auth_data, headers=headers, timeout=30)
        if response.status_code == 200:
            logging.info("NetDB Bearer token basariyla alindi.")
            return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        logging.error(f"NetDB Bearer token alma hatasi: {e}")
    return None

# Cihaz arayüz verilerini çekme
def get_device_interfaces(hostname, token):
    url = device_interfaces_url_template.format(hostname=hostname)
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logging.info(f"{hostname} arayüz verileri basariyla alindi.")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"{hostname} arayüz verileri alinamadi: {e}")
        return None

# Sadece `is_up = True` olan portlari filtreleme ve Mbps'ye çevirme
def filter_active_ports(interface_data):
    active_ports = []
    for interface_name, details in interface_data.get("results", {}).items():
        if details.get("is_up", False):
            input_rate_mbps = details.get("input_rate", 0) / 1_000_000  # Mbps
            output_rate_mbps = details.get("output_rate", 0) / 1_000_000  # Mbps

            active_ports.append({
                "Interface Name": interface_name,
                "Description": details.get("description", ""),
                "MAC Address": details.get("mac_address", ""),
                "Link Status": details.get("link_status", ""),
                "Protocol Status": details.get("protocol_status", ""),
                "Bandwidth": details.get("bandwidth", ""),
                "Input Rate (Mbps)": round(input_rate_mbps, 2),
                "Output Rate (Mbps)": round(output_rate_mbps, 2),
                "Input Packets": details.get("input_packets", ""),
                "Output Packets": details.get("output_packets", "")
            })
    return active_ports

# JSON ve Excel dosyasina kaydetme
def save_results_to_files(data, json_file, excel_file):
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    logging.info(f"Veri JSON dosyasina kaydedildi: {json_file}")

    df = pd.DataFrame(data["ports"])
    df.to_excel(excel_file, index=False)
    logging.info(f"Veri Excel dosyasina kaydedildi: {excel_file}")

# Ana islem
def main():
    logging.info("Islem baslatiliyor...")
    token = get_bearer_token()
    if not token:
        logging.error("Bearer token alinamadi, islem sonlandiriliyor.")
        return

    hostname = "TrCHO1104sw06"  # Test edilen hostname
    interface_data = get_device_interfaces(hostname, token)
    if not interface_data:
        logging.error(f"{hostname} için veri alinamadi, islem sonlandiriliyor.")
        return

    active_ports = filter_active_ports(interface_data)
    result_data = {
        "hostname": hostname,
        "last_updated": datetime.now().isoformat(),
        "ports": active_ports
    }

    save_results_to_files(result_data, output_json_file, output_excel_file)
    logging.info("Islem tamamlandi.")

if __name__ == "__main__":
    main()
