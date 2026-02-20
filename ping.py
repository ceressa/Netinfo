import requests
import json
import os
from datetime import datetime
from cryptography.fernet import Fernet

# 📁 Dosya yolları
CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"
INPUT_FILE = "D:/INTRANET/Netinfo/Data/network_device_inventory.json"
OUTPUT_JSON_FILE = "D:/INTRANET/Netinfo/Data/ping_results.json"

# 🌐 API URL'leri
API_URL = "https://network-api.npe.fedex.com/v1/tshoot/ping?hosts={host}&count=1&timeout=1500"
AUTH_URL = "https://network-api.npe.fedex.com/v1/authorize"


# 🔐 Şifreleme ve kimlik bilgileri yükleme
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
    """Şifrelenmiş kimlik bilgilerini JSON dosyasından okur."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("⚠️ Kimlik bilgileri dosyası bulunamadı.")

    with open(CREDENTIALS_FILE, 'r') as f:
        credentials = json.load(f)

    # JSON dosyanın "netdb" anahtarını kullandığını biliyoruz.
    netdb_credentials = credentials.get("netdb", {})

    if "username" not in netdb_credentials or "password" not in netdb_credentials:
        raise KeyError("❌ JSON dosyasında 'username' veya 'password' eksik!")

    return {
        "username": netdb_credentials["username"],  # Kullanıcı adı şifrelenmemiş zaten
        "password": decrypt_data(netdb_credentials["password"])  # Şifreyi çözüyoruz
    }


# 🔑 Bearer Token alma fonksiyonu
def get_bearer_token():
    creds = load_credentials()
    auth_data = {
        'grant_type': 'password',
        'username': creds["username"],
        'password': creds["password"]
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    response = requests.post(AUTH_URL, data=auth_data, headers=headers)

    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"❌ Token alınamadı! {response.status_code} - {response.text}")
        return None


# 📡 Ping atma fonksiyonu
def ping_host(ip, bearer_token):
    """API üzerinden verilen IP adresine ping atar ve sonucu döndürür."""
    try:
        url = API_URL.format(host=ip)
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {bearer_token}'
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ {ip} için veri alınamadı! {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ {ip} için hata oluştu: {e}")
        return None


# 📥 JSON'dan IP adreslerini oku
def load_ip_addresses():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"⚠️ Girdi dosyası bulunamadı: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as json_file:
        devices = json.load(json_file)

    return [device["ipaddress"] for device in devices if "ipaddress" in device]


# 📤 Sonuçları JSON olarak kaydet
def save_results_to_json(results, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"✅ Sonuçlar {filename} dosyasına kaydedildi.")
    except Exception as e:
        print(f"❌ JSON'a kaydederken hata oluştu: {e}")


# 🚀 Ana çalışma fonksiyonu
def main():
    print("📡 Ping testi başlatılıyor...")

    # Token al
    bearer_token = get_bearer_token()
    if not bearer_token:
        print("❌ Bearer token alınamadı! İşlem sonlandırılıyor.")
        return

    # IP adreslerini JSON dosyasından oku
    ip_addresses = load_ip_addresses()
    if not ip_addresses:
        print("⚠️ IP adresleri bulunamadı! İşlem sonlandırılıyor.")
        return

    # Sonuçları tutacak liste
    ping_results = {
        "timestamp": datetime.now().isoformat(),
        "results": []
    }

    # Ping işlemi yap
    for ip in ip_addresses:
        result = ping_host(ip, bearer_token)
        if result:
            for ip, data in result.get("results", {}).items():
                ping_results["results"].append({
                    "IP Address": ip,
                    "Success": data.get("success", False),
                    "Ping Count": data.get("count", 0),
                    "Timeout (ms)": data.get("timeout", 0),
                    "Permalink": result.get("permalink", "")
                })

    # Sonuçları JSON olarak kaydet
    if ping_results["results"]:
        save_results_to_json(ping_results, OUTPUT_JSON_FILE)
    else:
        print("❌ Hiç ping sonucu alınamadı!")


if __name__ == "__main__":
    main()
