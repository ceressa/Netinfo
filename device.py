import requests
import json
import os
import pandas as pd


def fetch_device_data(device_id):
    # API URL'si
    api_url = f"https://statseeker.emea.fedex.com/api/v2.1/cdt_port/?fields=deviceid,name,ifTitle,ifSpeed,ifDescr,ifAdminStatus,ifOperStatus,if90day&deviceid={device_id}"
    username = os.environ.get("STATSEEKER_USERNAME", "")
    password = os.environ.get("STATSEEKER_PASSWORD", "")

    if not username or not password:
        print("STATSEEKER_USERNAME ve STATSEEKER_PASSWORD environment variable'lari tanimlanmali.")
        return

    try:
        # API'ye istek gönder
        response = requests.get(api_url, auth=(username, password), verify=True)
        response.raise_for_status()
        data = response.json()

        # Veri işleme
        if not data.get("data") or not data["data"].get("objects"):
            raise ValueError("Beklenen veri yapısı mevcut değil.")

        device_data = data["data"]["objects"][0]["data"]

        if not device_data:
            raise ValueError("Belirtilen Device ID'ye ait veri bulunamadı.")

        # Veriyi DataFrame'e dönüştür
        df = pd.DataFrame(device_data)

        # Veriyi temizleme ve işleme
        if "ifSpeed" in df.columns:
            df["ifSpeed"] = df["ifSpeed"].fillna(0).astype(int) // 1000000  # Hızı Mbps'ye çevir
        if "if90day" in df.columns:
            df["if90day"] = df["if90day"].apply(lambda x: "Active" if x == 1 else "Inactive")
        if "ifOperStatus" in df.columns:
            oper_status_map = {
                "up": "Operational",
                "down": "Down",
                "testing": "Testing",
                "unknown": "Unknown",
                "dormant": "Dormant",
                "notPresent": "Not Present",
                "lowerLayerDown": "Lower Layer Down"
            }
            df["ifOperStatus"] = df["ifOperStatus"].map(oper_status_map).fillna("Unknown")

        # DataFrame'i Excel'e kaydetme
        output_file = f"device_{device_id}_data.xlsx"
        df.to_excel(output_file, index=False)
        print(f"Veri başarıyla {output_file} dosyasına kaydedildi.")

    except requests.exceptions.RequestException as e:
        print(f"API isteği sırasında hata oluştu: {e}")
    except ValueError as ve:
        print(f"Hata: {ve}")
    except Exception as ex:
        print(f"Beklenmeyen bir hata oluştu: {ex}")


if __name__ == "__main__":
    device_id = input("Lütfen Device ID giriniz: ")
    fetch_device_data(device_id)
