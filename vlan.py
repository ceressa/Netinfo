import requests
import pandas as pd
import logging
import urllib3

# Loglama yapılandırması
logging.basicConfig(
    filename=r"D:\INTRANET\Netinfo\Data\vlan_port_mapping.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# API Bilgileri
auth_url = "https://network-api.npe.fedex.com/v1/authorize"
interfaces_url = "https://network-api.npe.fedex.com/v1/device/TrCHO1104sw06/interfaces?device_type=cisco_ios"
vlans_url = "https://network-api.npe.fedex.com/v1/device/TrCHO1104sw06/vlans?device_type=cisco_ios"

# Kullanıcı Bilgileri
username = "3723002"
password = "Xerez386251-"
deviceid = "21998892"  # Statseeker'dan alınan deviceid

# Çıktı dosyası
output_file = r"D:\INTRANET\Netinfo\Data\vlan_port_mapping.xlsx"

# SSL Uyarılarını devre dışı bırak
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Bearer Token Alımı
def fetch_bearer_token():
    logging.info("Bearer token alınıyor...")
    auth_data = {'grant_type': 'password', 'username': username, 'password': password}
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
    try:
        response = requests.post(auth_url, data=auth_data, headers=headers, verify=False)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            logging.error("Bearer token alınamadı: %s", response.text)
            return None
        logging.info("Bearer token başarıyla alındı.")
        return token
    except requests.RequestException as e:
        logging.error("Token alımı sırasında hata: %s", e)
        return None

# VLAN Haritası Oluştur
def build_vlan_map(vlan_data):
    vlan_map = {}
    for vlan in vlan_data.get("results", []):
        vlan_id = vlan.get("vlan_id", "N/A")
        vlan_name = vlan.get("name", "N/A")
        for interface in vlan.get("interfaces", []):
            vlan_map[interface] = {"vlan_id": vlan_id, "vlan_name": vlan_name}
    logging.info("VLAN haritası oluşturuldu.")
    return vlan_map

# Port ve VLAN Bilgilerini Çek
def fetch_device_data(token):
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    try:
        # Port bilgileri
        logging.info("Port bilgileri çekiliyor...")
        ports_response = requests.get(interfaces_url, headers=headers, verify=False)
        ports_response.raise_for_status()
        ports_data = ports_response.json()
        logging.debug("Port bilgileri alındı.")
    except requests.RequestException as e:
        logging.error("Port bilgileri alınamadı: %s", e)
        ports_data = {}

    try:
        # VLAN bilgileri
        logging.info("VLAN bilgileri çekiliyor...")
        vlans_response = requests.get(vlans_url, headers=headers, verify=False)
        vlans_response.raise_for_status()
        vlan_data = vlans_response.json()
        logging.debug("VLAN bilgileri alındı.")
    except requests.RequestException as e:
        logging.error("VLAN bilgileri alınamadı: %s", e)
        vlan_data = {}

    return ports_data, vlan_data

# Veriyi Excel'e Kaydet
def save_vlan_port_mapping(vlan_map, ports_data):
    logging.info("Veriler Excel dosyasına kaydediliyor...")
    all_data = []

    # `results` bir listeyse:
    for port in ports_data.get("results", []):
        # Port bilgilerini kontrol et ve uygun şekilde işle
        if isinstance(port, dict) and port.get("name", "").startswith("Gi"):  # Sadece Gigabit Ethernet portları
            vlan_info = vlan_map.get(port["name"], {"vlan_id": "N/A", "vlan_name": "N/A"})
            all_data.append({
                "Device ID": deviceid,
                "Port Name": port["name"],
                "MAC Address": port.get("mac_address", "N/A"),
                "Link Status": port.get("link_status", "N/A"),
                "Description": port.get("description", "N/A"),
                "VLAN ID": vlan_info["vlan_id"],
                "VLAN Name": vlan_info["vlan_name"]
            })

    # Excel'e yazma
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_excel(output_file, index=False)
        logging.info("Veriler başarıyla %s dosyasına kaydedildi.", output_file)
    else:
        logging.warning("Hiçbir veri işlenemedi, çıktı dosyası oluşturulmadı.")


# Ana Fonksiyon
def main():
    token = fetch_bearer_token()
    if not token:
        logging.error("Token alınamadı. Çıkılıyor.")
        return

    ports_data, vlan_data = fetch_device_data(token)

    # VLAN haritası oluştur
    vlan_map = build_vlan_map(vlan_data)

    # Veriyi kaydet
    save_vlan_port_mapping(vlan_map, ports_data)

if __name__ == "__main__":
    main()
