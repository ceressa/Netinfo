import requests
import pandas as pd
from datetime import datetime
import pytz
import json
import urllib3

# SSL uyarılarını devre dışı bırakma (güvenlik açısından dikkatli kullanın)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API bağlantı bilgileri
base_url = 'https://statseeker.emea.fedex.com/api/v2.1/'
user = 'tr-api'
password = 'F3xpres!'

fields = {
    'device': 'id,deviceid,hostname,ipaddress,ping_state',
    'inventory': 'id,deviceid,serial,class,model'
}

# URL'leri oluşturma (ping_state_formats kaldırıldı)
urls = {
    name: f"{base_url}cdt_{name}?fields={fields[name]}&groups=NOC-Turkey&links=none&limit=100000"
    for name in fields
}


def fetch_data(url):
    """API'den veri çekme."""
    try:
        print(f"Fetching data from {url}")
        response = requests.get(url, auth=(user, password), verify=False, timeout=60)
        print(f"Response code: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching data from {url}: {response.status_code} {response.text}")
            return None
    except requests.exceptions.Timeout:
        print(f"Timeout error occurred while connecting to {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None



def process_data(data):
    """JSON verisini Pandas DataFrame'e dönüştürme."""
    if 'data' in data and 'objects' in data['data']:
        objects = data['data']['objects']
        if objects and isinstance(objects, list) and 'data' in objects[0]:
            return pd.DataFrame(objects[0]['data'])
    print("Unexpected data structure")
    return pd.DataFrame()


def update_data():
    """Verileri güncelle ve JSON ile Excel dosyalarına kaydet."""
    data_frames = {}

    # Her URL için veriyi çek ve işleme al
    for name, url in urls.items():
        print(f"\nFetching {name} data...")
        data = fetch_data(url)
        if data:
            df = process_data(data)
            data_frames[name] = df
            print(f"Fetched {len(df)} rows for {name}")
            print(df.head())
        else:
            print(f"Failed to fetch {name} data")

    # Cihaz ve envanter verilerini birleştirme
    if 'device' in data_frames and 'inventory' in data_frames:
        merged_data = data_frames['device'].merge(data_frames['inventory'], on='deviceid', how='left',
                                                  suffixes=('', '_inventory'))

        # Sadece chassis sınıfındaki cihazları filtreleme
        merged_data = merged_data[merged_data['class'] == 'chassis']

        # Ping state durumunu basitleştirme (sadece up veya down)
        merged_data['ping_state'] = merged_data['ping_state'].apply(
            lambda x: x if isinstance(x, str) else 'unknown'
        )

        # Son güncelleme zamanını ekleme
        merged_data['last_updated'] = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%d %B %Y %H:%M')

        # Gereksiz sütunları kaldırma
        columns_to_drop = ['id_inventory', 'class']
        merged_data = merged_data.drop([col for col in columns_to_drop if col in merged_data.columns], axis=1)

        print("\nMerged Data:")
        print(merged_data.head())
        print(f"\nTotal rows after filtering: {len(merged_data)}")

        # JSON dosyasına kaydetme
        json_file = 'D:/INTRANET/Netinfo/Data/statseeker_base.json'
        merged_data.to_json(json_file, orient='records', indent=2)
        print(f"\nData has been saved to {json_file}")

        # Excel dosyasına kaydetme
        excel_file = 'D:/INTRANET/Netinfo/Data/Statseeker_base.xlsx'
        merged_data.to_excel(excel_file, index=False)
        print(f"\nData has been saved to {excel_file}")


if __name__ == "__main__":
    update_data()