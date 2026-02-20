import requests
import pandas as pd
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time, sleep
import logging
import socket

# NetDB API Credentials
netdb_auth_url = "https://network-api.npe.fedex.com/v1/authorize"
netdb_device_url = "https://network-api.npe.fedex.com/v1/device/{hostname}/details?device_type=cisco_ios&config_type=running"
username = "3723002"
password = "Xerez386251-"

# Output File
output_excel_file = "D:/INTRANET/Netinfo/Data/Netdb_data.xlsx"

# Configure Logging
log_file = "D:/INTRANET/Netinfo/Data/fetch_netdb.log"
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_connectivity(hostname="network-api.npe.fedex.com", port=443):
    """Check connectivity to the API server."""
    try:
        logging.debug(f"Checking connectivity to {hostname}:{port}")
        socket.create_connection((hostname, port), timeout=5)
        logging.info(f"Successfully connected to {hostname}:{port}")
    except Exception as e:
        logging.error(f"Connectivity check failed for {hostname}:{port}: {e}")
        return False
    return True

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
        logging.debug("Requesting bearer token with auth_data: %s", auth_data)
        response = requests.post(netdb_auth_url, data=auth_data, headers=headers, timeout=60)
        logging.debug("Bearer token response: %s", response.text)
        response.raise_for_status()
        token = response.json().get('access_token')
        if not token:
            logging.error("No access_token found in response: %s", response.json())
            return None
        logging.info("Token fetched successfully. Expires in %s seconds.", response.json().get('expires_in', 'unknown'))
        return token
    except requests.exceptions.Timeout as e:
        logging.error("Timeout while fetching token: %s", e)
    except requests.exceptions.RequestException as e:
        logging.error("Error fetching bearer token: %s", e)
    return None

def fetch_device_details(hostname, token, retries=5, delay=30):
    """Fetch details of a single device by hostname with retry logic."""
    url = netdb_device_url.format(hostname=hostname)
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    for attempt in range(1, retries + 1):
        try:
            logging.debug("Fetching device details for hostname: %s, Attempt: %d", hostname, attempt)
            response = requests.get(url, headers=headers, timeout=60)
            logging.debug("Device details response: %s", response.text)
            response.raise_for_status()
            data = response.json()
            if "results" in data and "facts" in data["results"]:
                logging.info("Successfully fetched details for %s.", hostname)
                return {
                    "Hostname": data["results"]["facts"].get("hostname"),
                    "Model": data["results"]["facts"].get("model"),
                    "OS Version": data["results"]["facts"].get("os_version"),
                    "Serial Number": data["results"]["facts"].get("serial_number"),
                    "Uptime": data["results"]["facts"].get("uptime_string"),
                    "Vendor": data["results"]["facts"].get("vendor")
                }
        except requests.exceptions.Timeout as e:
            logging.warning("Timeout on attempt %d for %s: %s", attempt, hostname, e)
        except requests.exceptions.RequestException as e:
            logging.warning("Attempt %d failed for %s: %s", attempt, hostname, e)
        if attempt < retries:
            logging.info("Retrying %s after %d seconds...", hostname, delay)
            sleep(delay)
    logging.error("Failed to fetch details for hostname %s after %d attempts.", hostname, retries)
    return None

def fetch_all_devices_parallel(file_path):
    """Fetch details for all devices listed in an Excel file using parallel requests with delays."""
    start_time = time()
    logging.info("Starting fetch_all_devices_parallel.")

    if not check_connectivity():
        logging.error("Connectivity check failed. Exiting.")
        return

    token = fetch_bearer_token()
    if not token:
        logging.error("Token not available. Exiting.")
        return

    try:
        logging.debug("Reading device hostnames from file: %s", file_path)
        data = pd.read_excel(file_path)
        logging.debug("Excel data read successfully: %s", data.head())
        hostnames = data.iloc[:, 2].dropna().tolist()
    except FileNotFoundError:
        logging.error("File not found: %s", file_path)
        return
    except Exception as e:
        logging.error("Error reading the Excel file: %s", e)
        return

    filtered_hostnames = [hostname for hostname in hostnames if "SEG" not in hostname]
    logging.info("Filtered hostnames: %d out of %d", len(filtered_hostnames), len(hostnames))

    all_device_data = []

    with ThreadPoolExecutor(max_workers=3) as executor:  # Adjust worker count for stability
        futures = {executor.submit(fetch_device_details, hostname, token): hostname for hostname in filtered_hostnames}
        for future in as_completed(futures):
            hostname = futures[future]
            try:
                result = future.result()
                if result:
                    all_device_data.append(result)
            except Exception as e:
                logging.error("Error fetching data for hostname %s: %s", hostname, e)

    if all_device_data:
        save_to_excel(all_device_data, output_excel_file)
    else:
        logging.warning("No data fetched for any devices.")

    end_time = time()
    logging.info("Total execution time: %.2f seconds", end_time - start_time)

def save_to_excel(data, filename="device_data.xlsx"):
    """Save the collected data to an Excel file."""
    try:
        df = pd.DataFrame(data)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        df.to_excel(filename, index=False)
        logging.info("Data saved to %s", filename)
    except Exception as e:
        logging.error("Error saving data to Excel: %s", e)

if __name__ == "__main__":
    file_path = "D:/INTRANET/Netinfo/Data/Statseeker_Data.xlsx"
    fetch_all_devices_parallel(file_path)
