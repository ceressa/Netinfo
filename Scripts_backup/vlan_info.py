import requests
import json
import os
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from cryptography.fernet import Fernet

# **📌 Dosya yolları**
CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"
LOG_DIR = "D:/INTRANET/Netinfo/logs/Latest_Logs"
VLAN_DATA_FILE = "D:/INTRANET/Netinfo/Data/device_vlan_data.json"  # **📌 VLAN için yeni JSON dosyası**

# **📌 API URL ve Proxy Ayarları**
NETDB_AUTH_URL = "https://network-api.npe.fedex.com/v1/authorize"
NETDB_BASE_URL = "https://network-api.npe.fedex.com/v1/device/"

PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# **📌 Loglama Ayarları**
os.makedirs(LOG_DIR, exist_ok=True)
log_file_date = datetime.now().strftime('%Y%m%d')
log_file = os.path.join(LOG_DIR, f"vlan_fetch_{log_file_date}.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

def log_message(level, message):
    print(f"{level.upper()}: {message}")
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

# **📌 Şifreleme Anahtarı ve Kimlik Bilgilerini Yükleme**
def load_key():
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("❌ Secret key dosyası bulunamadı.")
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()

ENCRYPTION_KEY = load_key()

def decrypt_data(encrypted_data):
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_data.encode()).decode()

def load_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("❌ Credentials dosyası bulunamadı.")
    with open(CREDENTIALS_FILE, 'r') as f:
        credentials = json.load(f)
    return credentials

def get_netdb_credentials():
    credentials = load_credentials()
    username = credentials["netdb"]["username"]
    password = decrypt_data(credentials["netdb"]["password"])
    return username, password

def get_netdb_bearer_token():
    username, password = get_netdb_credentials()
    auth_data = {"grant_type": "password", "username": username, "password": password}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

    for attempt in range(3):
        response = None
        try:
            response = requests.post(NETDB_AUTH_URL, data=auth_data, headers=headers, proxies=PROXY, timeout=60)
            response.raise_for_status()
            token = response.json().get("access_token")
            if token:
                log_message("info", "✅ Token başarıyla alındı.")
                return token
            else:
                log_message("error", "❌ Token alınamadı: Yanıt içeriği boş.")
        except requests.RequestException as e:
            log_message("error", f"❌ Token alınamadı: {e}")
            if response is not None:
                log_message("error", f"Response Status Code: {response.status_code}")
                log_message("error", f"Response Content: {response.text}")

    raise RuntimeError("❌ Token alınamadı. Lütfen yetkileri kontrol edin.")

# **📌 Cihazdan VLAN Verisi Çekme**
def fetch_vlan_data(hostname, bearer_token):
    url = f"{NETDB_BASE_URL}{hostname}/vlans?device_type=cisco_ios"
    headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}

    log_message("info", f"📡 API çağrısı yapılıyor: {url}")

    try:
        response = requests.get(url, headers=headers, proxies=PROXY, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        log_message("error", f"❌ {hostname} için hata: {e.response.status_code} - {e.response.text}")
        return None
    except requests.RequestException as e:
        log_message("error", f"❌ {hostname} için ağ hatası: {e}")
        return None

# **📌 VLAN Verisini İşleme**
def process_vlan_info(vlan_data):
    vlans = {}

    results = vlan_data.get("results", [])
    for vlan in results:
        vlan_id = vlan.get("vlan_id")
        vlan_name = vlan.get("name")
        status = vlan.get("status", "unknown")

        if vlan_id:
            vlans[vlan_id] = {
                "vlan_id": vlan_id,
                "vlan_name": vlan_name,
                "status": status
            }

    return vlans

# **📌 Tüm Cihazlar İçin VLAN Verisi Çekme**
def update_vlan_data():
    log_message("info", "📌 VLAN verisi toplanıyor...")

    # **📌 Cihaz Listesini Yükle**
    with open("D:/INTRANET/Netinfo/Data/network_device_inventory.json", "r", encoding="utf-8") as f:
        devices = json.load(f)

    bearer_token = get_netdb_bearer_token()

    all_vlan_data = {}
    failed_devices = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_device = {executor.submit(fetch_vlan_data, device["hostname"], bearer_token): device for device in devices}

        for future in tqdm(as_completed(future_to_device), total=len(devices), desc="📡 VLAN Verisi Çekiliyor"):
            device = future_to_device[future]
            hostname = device["hostname"]
            device_id = device["deviceid"]

            try:
                vlan_data = future.result()
                if vlan_data and vlan_data.get("success"):
                    vlans = process_vlan_info(vlan_data)

                    all_vlan_data[hostname] = {
                        "hostname": hostname,
                        "deviceid": device_id,
                        "last_updated": datetime.now().isoformat(),
                        "vlans": vlans
                    }
                else:
                    log_message("error", f"⚠️ {hostname} VLAN bilgisi çekilemedi.")
                    failed_devices.append(hostname)
            except Exception as e:
                log_message("error", f"❌ {hostname} VLAN verisi işlenemedi: {e}")
                failed_devices.append(hostname)

    # **📌 JSON Dosyasına Kaydet**
    with open(VLAN_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_vlan_data, f, indent=2, ensure_ascii=False)

    log_message("info", "✅ VLAN veri toplama işlemi tamamlandı.")

    # **📌 Başarısız Olan Cihazları Listele**
    if failed_devices:
        log_message("error", f"❌ VLAN bilgisi alınamayan cihazlar: {', '.join(failed_devices)}")

# **📌 Ana Çalıştırıcı**
if __name__ == "__main__":
    update_vlan_data()
