import requests
import pandas as pd
import urllib3
from datetime import datetime
import pytz
import json
import os

base_url = 'https://statseeker.emea.fedex.com/api/v2.1/'
user = os.environ.get("STATSEEKER_USERNAME", "")
password = os.environ.get("STATSEEKER_PASSWORD", "")

fields = {
    'device': 'id,deviceid,hostname,ipaddress,ping_state',
    'inventory': 'id,deviceid,serial,class,model'
}

urls = {
    name: f"{base_url}cdt_{name}?fields={fields[name]}&groups=NOC-Turkey&links=none&limit=100000&ping_state_formats=state_time"
    for name in fields
}

def fetch_data(url):
    response = requests.get(url, auth=(user, password), verify=True)
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error fetching data from {url}: {response.status_code} {response.text}')
        return None

def process_data(data):
    if 'data' in data and 'objects' in data['data']:
        objects = data['data']['objects']
        if objects and isinstance(objects, list) and 'data' in objects[0]:
            return pd.DataFrame(objects[0]['data'])
    print("Unexpected data structure")
    return pd.DataFrame()

def format_uptime(timestamp):
    if pd.isna(timestamp):
        return "Bu cihaz ile ilgili güncel veriye ulaşılamadı."
    now = datetime.now(pytz.UTC)
    uptime = now - datetime.fromtimestamp(timestamp, pytz.UTC)
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days} gün, {hours} saat, {minutes} dakika"

def format_timestamp(x):
    if pd.isna(x):
        return "Bu cihaz ile ilgili güncel veriye ulaşılamadı."
    return datetime.fromtimestamp(x, pytz.timezone('Europe/Istanbul')).strftime('%d %B %Y %H:%M')

def update_data():
    data_frames = {}
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

    if 'device' in data_frames and 'inventory' in data_frames:
        merged_data = data_frames['device'].merge(data_frames['inventory'], on='deviceid', how='left',
                                                  suffixes=('', '_inventory'))
        merged_data = merged_data[merged_data['class'] == 'chassis']

        if 'ping_state' in merged_data.columns:
            merged_data['ping_state_formatted'] = merged_data['ping_state'].apply(
                lambda x: format_timestamp(x['state_time']) if isinstance(x, dict) and 'state_time' in x else "Bu cihaz ile ilgili güncel veriye ulaşılamadı.")
            merged_data['uptime'] = merged_data['ping_state'].apply(
                lambda x: format_uptime(x['state_time']) if isinstance(x, dict) and 'state_time' in x else "Bu cihaz ile ilgili güncel veriye ulaşılamadı.")
            merged_data['status'] = merged_data['ping_state'].apply(
                lambda x: 'Çalışıyor' if isinstance(x, dict) and x.get('state') == 'up' else 'Çalışmıyor')
            merged_data['ping_state'] = merged_data['ping_state'].apply(json.dumps)

        merged_data['last_updated'] = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%d %B %Y %H:%M')

        columns_to_drop = ['id_inventory', 'class']
        merged_data = merged_data.drop([col for col in columns_to_drop if col in merged_data.columns], axis=1)

        print("\nMerged Data:")
        print(merged_data.head())
        print(f"\nTotal rows after filtering: {len(merged_data)}")

        # Save the data to the Excel file
        excel_file = 'D:/INTRANET/Netinfo/Data/merged_statseeker_data.xlsx'
        merged_data.to_excel(excel_file, index=False)
        print(f"\nData has been saved to {excel_file}")

        return merged_data
    else:
        print("Device or Inventory data could not be fetched or processed completely.")
        return None

if __name__ == "__main__":
    update_data()