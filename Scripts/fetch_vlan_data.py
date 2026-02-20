import requests
import logging
import pandas as pd
import urllib3
import os
from dotenv import load_dotenv

load_dotenv()

# API Bilgileri
auth_url = "https://network-api.npe.fedex.com/v1/authorize"
vlan_url_template = "https://network-api.npe.fedex.com/v1/device/{hostname}/vlans?device_type=cisco_ios"
username = os.environ.get("NETDB_USERNAME")
password = os.environ.get("NETDB_PASSWORD")
SSL_VERIFY = os.environ.get("SSL_CERT_PATH", True)

# �ikti dosyasi
vlan_output_file = "D:/INTRANET/Netinfo/Data/all_devices_vlan.xlsx"
statseeker_file = "D:/INTRANET/Netinfo/Data/statseeker_data.xlsx"

# Log yapilandirmasi
logging.basicConfig(
    filename="D:/INTRANET/Netinfo/Data/all_devices_vlan.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# SSL Uyarilarini Devre Disi Birakma
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Bearer Token Alimi
def fetch_bearer_token():
    auth_data = {'grant_type': 'password', 'username': username, 'password': password}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
    try:
        response = requests.post(auth_url, data=auth_data, headers=headers, verify=SSL_VERIFY)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            logging.error("Bearer token alinamadi, response: %s", response.text)
            return None
        return token
    except requests.exceptions.SSLError as ssl_err:
        logging.error("SSL sertifikasi dogrulama hatasi: %s", ssl_err)
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error("Token alimi sirasinda hata olustu: %s", req_err)
        return None

# VLAN Bilgilerini �ekme
def fetch_vlan_info(hostname, token):
    url = vlan_url_template.format(hostname=hostname)
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, verify=SSL_VERIFY)
        response.raise_for_status()
        vlan_data = response.json()
        logging.info(f"Successfully fetched VLAN data for {hostname}.")
        return vlan_data
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch VLAN info for {hostname}: {e}")
        return None

# Veriyi Excel'e Kaydetme
def save_to_excel(all_vlan_data):
    if all_vlan_data:
        df = pd.DataFrame(all_vlan_data)
        df.to_excel(vlan_output_file, index=False)
        logging.info(f"T�m cihazlarin VLAN bilgileri {vlan_output_file} dosyasina kaydedildi.")
    else:
        logging.warning("Hi�bir cihaz i�in VLAN datasi kaydedilmedi.")

# Ana Fonksiyon
def main():
    token = fetch_bearer_token()
    if not token:
        logging.error("Token alinamadi. �ikiliyor.")
        return

    try:
        statseeker_df = pd.read_excel(statseeker_file)
        hostnames = statseeker_df["hostname"].dropna().tolist()
    except Exception as e:
        logging.error(f"Statseeker dosyasi okunurken hata olustu: {e}")
        return

    all_vlan_data = []
    for hostname in hostnames:
        vlan_data = fetch_vlan_info(hostname, token)
        if vlan_data and 'results' in vlan_data:
            for vlan in vlan_data["results"]:
                vlan_id = vlan.get("vlan_id", "N/A")
                vlan_name = vlan.get("name", "N/A")
                interfaces = vlan.get("interfaces", [])
                for interface in interfaces:
                    all_vlan_data.append({
                        "hostname": hostname,
                        "interface": interface,
                        "vlan_id": vlan_id,
                        "vlan_name": vlan_name
                    })

    save_to_excel(all_vlan_data)

if __name__ == "__main__":
    main()
