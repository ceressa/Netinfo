import requests
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

SSL_VERIFY = os.environ.get("SSL_CERT_PATH", True)

# Mevcut dosyandan import et
sys.path.append('D:/INTRANET/Netinfo/Scripts')

# Mevcut ap_data.py'den token fonksiyonunu kullan
from cryptography.fernet import Fernet

# File paths
CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"

PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}


def load_key():
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()


def decrypt_data(encrypted_data):
    ENCRYPTION_KEY = load_key()
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_data.encode()).decode()


def get_token():
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            credentials = json.load(f)

        username = credentials["netdb"]["username"]
        password = decrypt_data(credentials["netdb"]["password"])

        auth_url = "https://network-api.npe.fedex.com/v1/authorize"
        auth_data = {"grant_type": "password", "username": username, "password": password}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(auth_url, data=auth_data, headers=headers,
 timeout=60, verify=SSL_VERIFY)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Auth error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Token error: {e}")
    return None


def test_all_endpoints():
    print("Token alınıyor...")
    token = get_token()
    if not token:
        print("❌ Token alınamadı!")
        return

    print("✅ Token alındı, endpoint'ler test ediliyor...")

    BASE_URL = "https://network-api.npe.fedex.com/v1/device/"
    HOSTNAME = "TrISTRT2-SEG15"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    endpoints = {
        "wireless_clients": f"{BASE_URL}{HOSTNAME}/wireless-clients?device_type=extreme_wing&rf_domain=self",
        "cli_verbose": f"{BASE_URL}{HOSTNAME}/cli?device_type=extreme_wing&commands=show%20wireless%20clients%20verbose",
        "cli_station": f"{BASE_URL}{HOSTNAME}/cli?device_type=extreme_wing&commands=show%20station-table",
        "facts": f"{BASE_URL}{HOSTNAME}/facts?device_type=extreme_wing",
        "wireless_radios": f"{BASE_URL}{HOSTNAME}/wireless-radios?device_type=extreme_wing&rf_domain=self",
        "neighbors": f"{BASE_URL}{HOSTNAME}/neighbors?device_type=extreme_wing"
    }

    results = {}

    for name, url in endpoints.items():
        print(f"\n🔍 Testing: {name}")
        try:
            response = requests.get(url, headers=headers, timeout=30, verify=SSL_VERIFY)

            if response.status_code == 200:
                data = response.json()
                success = data.get('success', False)
                has_data = bool(data.get('results'))

                if success and has_data:
                    results[name] = data
                    print(f"✅ SUCCESS - Data bulundu!")

                    # Data analizi
                    results_data = data['results']
                    if isinstance(results_data, list):
                        print(f"   📊 {len(results_data)} item(s)")
                        if len(results_data) > 0 and isinstance(results_data[0], dict):
                            keys = list(results_data[0].keys())
                            print(f"   🔑 Keys: {keys[:5]}{'...' if len(keys) > 5 else ''}")
                    elif isinstance(results_data, dict):
                        print(f"   🔑 Dict keys: {list(results_data.keys())[:5]}")

                else:
                    print(f"❌ No data - success:{success}, has_results:{has_data}")
            else:
                print(f"❌ HTTP {response.status_code}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Sonuçları kaydet
    if results:
        output_file = "D:/INTRANET/Netinfo/Data/endpoint_test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n✅ {len(results)} başarılı endpoint bulundu!")
        print(f"📁 Sonuçlar: {output_file}")

        # Özet
        print(f"\n{'=' * 50}")
        print("📋 BAŞARILI ENDPOINT'LER:")
        for name in results.keys():
            print(f"   ✅ {name}")

    else:
        print("\n❌ Hiçbir endpoint'te data bulunamadı!")


if __name__ == "__main__":
    test_all_endpoints()
