import requests
import pandas as pd
from datetime import datetime
import os
import urllib3

# Statseeker API ayarları
base_url = "https://statseeker.emea.fedex.com/api/v2.1/cdt_port/"
auth = (os.environ.get("STATSEEKER_USERNAME", ""), os.environ.get("STATSEEKER_PASSWORD", ""))
fields = ["deviceid", "name", "ifTitle", "ifSpeed", "ifDescr", "ifAdminStatus", "if90day"]
group = "NOC-Turkey"
output_file = "port_data.xlsx"


def fetch_all_ports():
    """Statseeker API'den port verilerini çeker."""
    offset = 0
    limit = 100
    all_data = []

    while True:
        # API çağrısı için gerekli parametreler
        fields_param = "&".join([f"fields={field}" for field in fields])
        url = f"{base_url}?{fields_param}&groups={group}&limit={limit}&offset={offset}"
        response = requests.get(url, auth=auth, verify=True)

        if response.status_code != 200:
            print(f"Hata: {response.status_code} - {response.text}")
            break

        json_data = response.json()
        if "data" in json_data and "objects" in json_data["data"]:
            objects = json_data["data"]["objects"]
            if objects and "data" in objects[0]:
                data = objects[0]["data"]
                all_data.extend(data)

        # Daha fazla veri yoksa döngüden çık
        if not json_data["links"] or "next" not in [link["rel"] for link in json_data["links"]]:
            break

        offset += limit  # Sonraki sayfaya geç

    # Verileri pandas DataFrame'e çevir
    if all_data:
        return pd.DataFrame(all_data)
    else:
        print("Hiç veri alınamadı.")
        return pd.DataFrame()


def update_excel_file(new_data):
    """Excel dosyasını günceller veya oluşturur."""
    # Eğer dosya varsa mevcut veriyi yükle
    if os.path.exists(output_file):
        old_data = pd.read_excel(output_file)
    else:
        old_data = pd.DataFrame()

    # Yeni verileri eski verilerle birleştir
    combined_data = pd.concat([old_data, new_data]).drop_duplicates(subset=["deviceid", "name"], keep="last")

    # Sadece en son güncellenen verileri sakla
    combined_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Excel'e yaz
    combined_data.to_excel(output_file, index=False)
    print(f"{output_file} dosyası güncellendi.")


if __name__ == "__main__":
    print("Port verilerini çekiyor...")
    port_data = fetch_all_ports()
    if not port_data.empty:
        print("Veriler çekildi, dosya güncelleniyor...")
        update_excel_file(port_data)
    else:
        print("Hiç veri çekilemedi, işlem iptal edildi.")
