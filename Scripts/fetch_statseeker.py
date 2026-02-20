import requests
import json
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

username = os.environ.get("STATSEEKER_USERNAME")
password = os.environ.get("STATSEEKER_PASSWORD")
SSL_VERIFY = os.environ.get("SSL_CERT_PATH", True)

def fetch_device_data():
    # API URL'si
    api_url = "https://statseeker.emea.fedex.com/api/v2.1/cdt_device?fields=deviceid,hostname,ipaddress&groups=NOC-Turkey&links=none&limit=100000&ping_state_formats=state_time"

    try:
        # API'ye istek g�nder
        response = requests.get(api_url, auth=(username, password), verify=SSL_VERIFY)
        response.raise_for_status()
        data = response.json()

        # Veri isleme
        if not data.get("objects"):
            raise ValueError("Beklenen veri yapisi mevcut degil.")

        device_data = data["objects"]

        if not device_data:
            raise ValueError("Belirtilen cihazlara ait veri bulunamadi.")

        # SEG i�eren cihazlari filtrele
        filtered_data = [device for device in device_data if "SEG" not in device.get("hostname", "")]

        # Veriyi DataFrame'e d�n�st�r
        df = pd.DataFrame(filtered_data)

        # S�tunlari d�zenleme
        if 'data' in df.columns:
            df = pd.json_normalize(df['data'])

        df = df[['deviceid', 'hostname', 'ipaddress']]

        # DataFrame'i Excel'e kaydetme
        output_dir = "D:/INTRANET/Netinfo/Data"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "Statseeker_data.xlsx")
        df.to_excel(output_file, index=False)
        print(f"Veri basariyla {output_file} dosyasina kaydedildi.")

    except requests.exceptions.RequestException as e:
        print(f"API istegi sirasinda hata olustu: {e}")
    except ValueError as ve:
        print(f"Hata: {ve}")
    except Exception as ex:
        print(f"Beklenmeyen bir hata olustu: {ex}")

if __name__ == "__main__":
    fetch_device_data()
