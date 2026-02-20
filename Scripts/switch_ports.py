import pytz
import requests
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import os
import time
from functools import lru_cache
from cryptography.fernet import Fernet
from macarna import mac_lookup

# File paths
CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"
LOG_DIR = "D:/INTRANET/Netinfo/logs/Latest_Logs"

TURKEY_TZ = pytz.timezone("Europe/Istanbul")

# API and input/output paths
NETDB_AUTH_URL = "https://network-api.npe.fedex.com/v1/authorize"
NETDB_BASE_URL = "https://network-api.npe.fedex.com/v1/device/"
INPUT_FILE = "D:/INTRANET/Netinfo/Data/network_device_inventory.json"
OUTPUT_JSON_FILE = "D:/INTRANET/Netinfo/Data/main_data.json"

# Proxy settings
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# Loglama ayarları
os.makedirs(LOG_DIR, exist_ok=True)
log_file_date = datetime.now().strftime('%Y%m%d')
log_file = os.path.join(LOG_DIR, f"switch_ports_{log_file_date}.log")
log_start_time = datetime.now()

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

def log_message(level, message):
    """
    Loglama işlemleri için kısa bir wrapper.
    Bir gün geçtikten sonra log yazmayı durdurur.
    """
    global log_start_time
    if datetime.now() - log_start_time > timedelta(days=1):
        logging.shutdown()
        return
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)
    elif level == "debug":
        logging.debug(message)
    else:
        logging.info(message)

# Encryption and credentials handling
def load_key():
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("Secret key file not found.")
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()

ENCRYPTION_KEY = load_key()

def decrypt_data(encrypted_data):
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_data.encode()).decode()

def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("Credentials file not found.")
    with open(CREDENTIALS_FILE, 'r') as f:
        credentials = json.load(f)
    return credentials

@lru_cache(maxsize=1)
def get_netdb_credentials():
    credentials = load_credentials()
    username = credentials["netdb"]["username"]
    password = decrypt_data(credentials["netdb"]["password"])
    return username, password

@lru_cache(maxsize=1)
def get_netdb_bearer_token():
    username, password = get_netdb_credentials()
    auth_data = {"grant_type": "password", "username": username, "password": password}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

    for attempt in range(3):
        try:
            response = requests.post(NETDB_AUTH_URL, data=auth_data, headers=headers, timeout=60)
            response.raise_for_status()
            token = response.json().get("access_token")
            if token:
                log_message("info", "Token successfully retrieved.")
                return token
        except requests.RequestException as e:
            log_message("error", f"Error retrieving token: {e}")
    raise RuntimeError("Failed to obtain bearer token after multiple attempts.")

def fetch_device_data(hostname, bearer_token, timeout=60):
    """
    Belirtilen hostname için cihaz verilerini alır.
    """
    log_message("info", f"Cihaz verileri alınıyor: {hostname}")
    urls = {
        "interfaces": f"{NETDB_BASE_URL}{hostname}/interfaces?device_type=cisco_ios",
        "vlans": f"{NETDB_BASE_URL}{hostname}/vlans?device_type=cisco_ios",
        "neighbors": f"{NETDB_BASE_URL}{hostname}/neighbors?device_type=cisco_ios",
        "mac_address_table": f"{NETDB_BASE_URL}{hostname}/mac-address-table?device_type=cisco_ios"
    }
    headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}
    results = {}

    for key, url in urls.items():
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            results[key] = response.json().get("results", {})
            log_message("info", f"{key.capitalize()} verileri başarıyla alındı: {hostname}")
        except requests.RequestException as e:
            log_message("error", f"{key.capitalize()} verileri alınırken hata oluştu: {hostname}, Hata: {str(e)}")

    if len(results) == 4:
        return results
    return None

def get_main_data_last_modified():
    file_path = OUTPUT_JSON_FILE  # JSON dosyasının yolu

    if os.path.exists(file_path):
        modified_time = os.path.getmtime(file_path)  # Unix timestamp olarak al
        modified_datetime = datetime.fromtimestamp(modified_time, pytz.utc)  # UTC olarak al
        turkey_time = modified_datetime.astimezone(TURKEY_TZ)  # Türkiye saatine çevir

        return turkey_time.strftime('%d.%m.%Y %H:%M')  # TR formatında döndür

    return "Bilinmiyor"  # Dosya yoksa düzgün mesaj döndür

# Fonksiyonu çalıştır ve logla
MAIN_DATA_LAST_MODIFIED = get_main_data_last_modified()
log_message("info", f"Main Data Last Modified: {MAIN_DATA_LAST_MODIFIED}")


def process_vlan_data(vlan_data):
    """
    VLAN verilerini işler ve interface'leri VLAN'larla eşleştirir.
    Aynı zamanda switchport mode'unu da kontrol eder.
    """
    vlan_map = {}

    # Debug için VLAN data yapısını logla
    log_message("debug", f"VLAN Data Structure: {json.dumps(vlan_data[:2] if vlan_data else [], indent=2)}")

    for vlan in vlan_data:
        vlan_id = vlan.get('vlan_id', 'N/A')
        vlan_name = vlan.get('name', 'N/A')

        # Interface'leri kontrol et
        interfaces = vlan.get('interfaces', [])
        if not interfaces:
            # Alternatif alan isimleri kontrol et
            interfaces = vlan.get('ports', []) or vlan.get('members', []) or []

        log_message("debug", f"VLAN {vlan_id}: {len(interfaces)} interface found")

        for interface in interfaces:
            # Interface ismini normalize et
            normalized_interface = normalize_interface_name(interface)
            vlan_map[normalized_interface] = {
                'vlan_id': str(vlan_id),
                'vlan_name': str(vlan_name)
            }

            # Debug log
            log_message("debug", f"Mapped: {interface} -> {normalized_interface} = VLAN {vlan_id}")

    log_message("info", f"VLAN mapping tamamlandı. Toplam {len(vlan_map)} interface mapped.")
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
    if name.startswith("Gi"):
        return name.replace("Gi", "GigabitEthernet")
    elif name.startswith("Te"):
        return name.replace("Te", "TenGigabitEthernet")
    return name


def process_device_data(row, bearer_token):
    hostname = row["hostname"]
    device_id = row["deviceid"]
    log_message("info", f"{hostname} işleniyor...")

    for attempt in range(3):
        device_data = fetch_device_data(hostname, bearer_token)
        if device_data:
            break
        log_message("warning", f"Veri alınamadı: {hostname}, Deneme: {attempt + 1}")

    if not device_data:
        log_message("error", f"Tüm denemeler başarısız oldu: {hostname}")
        return None

    interfaces_data = device_data.get("interfaces", {})
    vlans_data = device_data.get("vlans", [])
    neighbors_data = device_data.get("neighbors", {})
    mac_address_table = device_data.get("mac_address_table", [])

    # Debug: VLAN data'yı logla
    log_message("info", f"{hostname} - VLAN sayısı: {len(vlans_data)}")
    log_message("info", f"{hostname} - Interface sayısı: {len(interfaces_data)}")

    vlan_map = process_vlan_data(vlans_data)
    processed_mac_table = process_mac_table(mac_address_table)

    port_data = []

    for interface_name, interface_details in interfaces_data.items():
        # VLAN mapping'i kontrol et
        vlan_info = vlan_map.get(interface_name, {"vlan_id": "N/A", "vlan_name": "N/A"})

        # Eğer VLAN bulunamadıysa alternatif yöntemler dene
        if vlan_info["vlan_id"] == "N/A":
            # Interface detail'lerde VLAN bilgisi var mı kontrol et
            if "vlan" in interface_details:
                vlan_info = {
                    "vlan_id": str(interface_details.get("vlan", "N/A")),
                    "vlan_name": "N/A"
                }
            elif "switchport_mode" in interface_details:
                mode = interface_details.get("switchport_mode", "").lower()
                if "trunk" in mode:
                    vlan_info = {"vlan_id": "TRUNK", "vlan_name": "Trunk Port"}
                elif "access" in mode:
                    access_vlan = interface_details.get("access_vlan", "N/A")
                    vlan_info = {
                        "vlan_id": str(access_vlan) if access_vlan != "N/A" else "1",
                        "vlan_name": "Access Port"
                    }

        neighbor_info = neighbors_data.get(interface_name, {})

        input_rate_mbps = interface_details.get("input_rate", 0) / 1_000_000
        output_rate_mbps = interface_details.get("output_rate", 0) / 1_000_000

        # Debug: Her port için VLAN bilgisini logla
        if vlan_info["vlan_id"] != "N/A":
            log_message("debug", f"{hostname} - {interface_name}: VLAN {vlan_info['vlan_id']}")

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
            "output_packets": interface_details.get("output_packets", ""),
            "last_input": interface_details.get("last_input", "N/A"),
            "last_output": interface_details.get("last_output", "N/A"),
            "last_output_hang": interface_details.get("last_output_hang", "N/A")
        })

    log_message("info", f"{hostname} işleme tamamlandı. {len(port_data)} port bulundu.")
    return {hostname: {"last_updated": datetime.now().isoformat(), "ports": port_data}}


def fetch_network_data():
    start_time = time.time()
    log_message("info", "Ağ veri toplama işlemi başlatılıyor...")

    with open(INPUT_FILE, "r", encoding="utf-8") as json_file:
        df = pd.DataFrame(json.load(json_file))  # JSON verisini DataFrame'e çevir

    # Sadece hostname içinde 'sw' geçenleri al, router'ları filtrele
    switches = df[df["hostname"].str.contains("sw", case=False, na=False)]

    bearer_token = get_netdb_bearer_token()
    if not bearer_token:
        log_message("error", "NetDB Bearer token alınamadı. İşlem sonlandırılıyor.")
        return

    all_data = {}
    failed_devices = []

    # 📌 **Switch Bazlı Trafik Verileri**
    switch_traffic_summary = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_switch = {executor.submit(process_device_data, row, bearer_token): row for _, row in
                            switches.iterrows()}

        for future in tqdm(as_completed(future_to_switch), total=len(switches), desc="Cihaz verileri işleniyor"):
            row = future_to_switch[future]
            try:
                result = future.result()
                if result:
                    all_data.update(result)

                    # 📌 **Her Switch için Toplam Input & Output Mbps Hesaplama**
                    hostname = row["hostname"]
                    ports = result[hostname]["ports"]

                    total_input = sum(port["input_rate_mbps"] for port in ports)
                    total_output = sum(port["output_rate_mbps"] for port in ports)

                    switch_traffic_summary[hostname] = {
                        "input_mbps": round(total_input, 2),
                        "output_mbps": round(total_output, 2)
                    }

                else:
                    failed_devices.append(row["hostname"])
            except Exception as e:
                failed_devices.append(row["hostname"])
                log_message("error", f"{row['hostname']} cihazı işlenirken hata oluştu: {e}")

    if failed_devices:
        log_message("warning", f"Veri alınamayan cihazlar: {', '.join(failed_devices)}")

    # 📌 **Genel Toplam Hesaplama**
    cumulated_input_mbps = round(sum(switch["input_mbps"] for switch in switch_traffic_summary.values()), 2)
    cumulated_output_mbps = round(sum(switch["output_mbps"] for switch in switch_traffic_summary.values()), 2)

    # 📌 **Son veri güncelleme saatini Türkiye saatine göre al**
    last_whole_data_updated = datetime.now(pytz.utc).astimezone(TURKEY_TZ).strftime('%d.%m.%Y %H:%M')

    # 📌 **JSON dosyasını kaydederken tüm verileri ekle**
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_whole_data_updated": last_whole_data_updated,  # Türkiye saatine göre güncellenmiş zaman
            "cumulated_input_mbps": cumulated_input_mbps,  # 🔥 Toplam giriş trafiği
            "cumulated_output_mbps": cumulated_output_mbps,  # 🔥 Toplam çıkış trafiği
            "switch_traffic_summary": switch_traffic_summary,  # 🔥 Switch bazlı giriş/çıkış verileri
            "data": all_data  # Tüm cihaz verileri
        }, f, indent=2, ensure_ascii=False)

    log_message("info", f"🔄 Veriler başarıyla güncellendi! Son güncelleme: {last_whole_data_updated}")
    log_message("info", f"📊 Toplam Giriş Trafiği: {cumulated_input_mbps} Mbps")
    log_message("info", f"📊 Toplam Çıkış Trafiği: {cumulated_output_mbps} Mbps")

    end_time = time.time()
    log_message("info", f"Ağ veri toplama işlemi tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")


if __name__ == "__main__":
    fetch_network_data()
