import requests
import pandas as pd
import os
from datetime import datetime

# NetDB API Credentials
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_device_url = "https://network-api.npe.fedex.com/v1/device/{hostname}/details?device_type=cisco_ios&config_type=running"
username = "3723002"
password = "Xerez386251-"

# Input and Output Files
input_excel_file = "D:/INTRANET/Netinfo/Data/merged_statseeker_data.xlsx"  # Hostname'lerin bulunduğu Excel dosyası
output_excel_file = "D:/INTRANET/Netinfo/Data/netdb_device_details.xlsx"  # NetDB detaylarının kaydedileceği Excel dosyası

# Fetch Bearer Token
def fetch_bearer_token():
    auth_data = {
        'grant_type': 'password',
        'username': username,
        'password': password
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    try:
        response = requests.post(netdb_auth_url, data=auth_data, headers=headers)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"Failed to fetch token: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error fetching bearer token: {e}")
    return None

# Fetch Device Details
def fetch_device_details(hostname, token):
    url = netdb_device_url.format(hostname=hostname)
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch device details for {hostname}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error fetching device details for {hostname}: {e}")
    return None

# Save Data to Excel
def save_to_excel(data):
    try:
        df = pd.DataFrame(data)
        os.makedirs(os.path.dirname(output_excel_file), exist_ok=True)
        df.to_excel(output_excel_file, index=False)
        print(f"Data successfully saved to {output_excel_file}")
    except Exception as e:
        print(f"Error saving data to Excel: {e}")

# Main Function
def main():
    # Read hostname list from input Excel file
    if not os.path.exists(input_excel_file):
        print(f"Input file not found: {input_excel_file}")
        return

    try:
        input_data = pd.read_excel(input_excel_file)
        if 'hostname' not in input_data.columns:
            print("Hostname column not found in input Excel file.")
            return

        hostnames = input_data['hostname'].dropna().tolist()
    except Exception as e:
        print(f"Error reading input Excel file: {e}")
        return

    # Fetch Bearer Token
    token = fetch_bearer_token()
    if not token:
        print("Token not available. Exiting.")
        return

    device_data = []

    # Fetch details for each hostname
    for hostname in hostnames:
        print(f"Fetching data for hostname: {hostname}")
        device_details = fetch_device_details(hostname, token)

        if device_details and "facts" in device_details:
            device_info = device_details["facts"]
            device_data.append({
                "Hostname": device_info.get("hostname"),
                "Model": device_info.get("model"),
                "OS Version": device_info.get("os_version"),
                "Serial Number": device_info.get("serial_number"),
                "Vendor": device_info.get("vendor"),
                "Uptime": device_info.get("uptime_string"),
            })

    if device_data:
        save_to_excel(device_data)
    else:
        print("No data fetched.")

if __name__ == "__main__":
    main()
