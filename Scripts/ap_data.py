import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import json
import urllib3
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from functools import lru_cache
from cryptography.fernet import Fernet
import time

sys.stdout.reconfigure(encoding='utf-8')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# File paths for NetDB authentication
CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"

# Proxy settings
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# Statseeker API connection details
statseeker_base_url = 'https://statseeker.emea.fedex.com/api/v2.1/'
statseeker_user = 'tr-api'
statseeker_password = 'F3xpres!'

# NetDB API URLs
NETDB_AUTH_URL = "https://network-api.npe.fedex.com/v1/authorize"
NETDB_BASE_URL = "https://network-api.npe.fedex.com/v1/device/"

# Log settings
log_directory = "D:/INTRANET/Netinfo/Logs/Latest_Logs"
os.makedirs(log_directory, exist_ok=True)

log_start_date = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y%m%d")
log_file_path = os.path.join(log_directory, f"access_point_inventory_{log_start_date}.log")

# Performance tracking
start_time = time.time()


def log_message(message):
    """Write log messages to a file and console."""
    global log_start_date, log_file_path
    current_date = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y%m%d')

    if current_date != log_start_date:
        log_start_date = current_date
        log_file_path = os.path.join(log_directory, f"access_point_inventory_{current_date}.log")

    timestamp = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y-%m-%d %H:%M:%S')
    elapsed = time.time() - start_time
    log_entry = f"{timestamp} [{elapsed:.1f}s] - {message}\n"

    try:
        with open(log_file_path, 'a', encoding='utf-8') as log_file:
            log_file.write(log_entry)
        print(f"LOG: {message}")
    except Exception as e:
        print(f"ERROR: Log dosyasına yazılırken hata oluştu: {e}")


# NetDB Authentication functions (unchanged)
def load_key():
    """Load encryption key from file."""
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError(f"Secret key file not found: {KEY_FILE}")
    with open(KEY_FILE, 'rb') as key_file:
        return key_file.read()


def decrypt_data(encrypted_data):
    """Decrypt encrypted data using Fernet."""
    try:
        ENCRYPTION_KEY = load_key()
        cipher = Fernet(ENCRYPTION_KEY)
        return cipher.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        log_message(f"Decryption error: {e}")
        return None


def load_credentials():
    """Load credentials from JSON file."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"Credentials file not found: {CREDENTIALS_FILE}")
    with open(CREDENTIALS_FILE, 'r') as f:
        credentials = json.load(f)
    return credentials


@lru_cache(maxsize=1)
def get_netdb_credentials():
    """Get NetDB credentials with caching."""
    try:
        credentials = load_credentials()
        username = credentials["netdb"]["username"]
        password = decrypt_data(credentials["netdb"]["password"])
        return username, password
    except Exception as e:
        log_message(f"NetDB credentials error: {e}")
        return None, None


@lru_cache(maxsize=1)
def get_netdb_bearer_token():
    """Get NetDB bearer token with retry logic."""
    username, password = get_netdb_credentials()
    if not username or not password:
        log_message("NetDB credentials not available")
        return None

    auth_data = {"grant_type": "password", "username": username, "password": password}
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

    for attempt in range(3):
        try:
            response = requests.post(NETDB_AUTH_URL, data=auth_data, headers=headers, timeout=60)
            response.raise_for_status()
            token = response.json().get("access_token")
            if token:
                log_message("NetDB Token successfully retrieved.")
                return token
        except requests.RequestException as e:
            log_message(f"NetDB token error (attempt {attempt + 1}): {e}")

    log_message("Failed to obtain NetDB bearer token after multiple attempts.")
    return None


def fetch_statseeker_ap_data():
    """Fetch AP data from Statseeker."""
    url = f"{statseeker_base_url}cdt_device?fields=id,deviceid,name,ipaddress,sysName,sysDescr,sysObjectID,sysContact,sysLocation&groups=NOC-Turkey&links=none&limit=10000"

    try:
        log_message(f"Fetching data from Statseeker: NOC-Turkey group")
        response = requests.get(url, auth=(statseeker_user, statseeker_password), verify=False, timeout=60,
)

        if response.status_code == 200:
            data = response.json()

            if 'data' in data and 'objects' in data['data']:
                objects = data['data']['objects']
                if objects and isinstance(objects, list) and len(objects) > 0 and 'data' in objects[0]:
                    df = pd.DataFrame(objects[0]['data'])

                    # Filter for SEG devices only
                    if 'name' in df.columns:
                        initial_count = len(df)
                        seg_devices = df[df['name'].str.contains('SEG', case=False, na=False)]
                        log_message(f"Statseeker: {initial_count} total devices, {len(seg_devices)} SEG devices found")
                        return seg_devices
                    else:
                        log_message("ERROR: 'name' column not found in Statseeker data")
                        return pd.DataFrame()
            else:
                log_message("ERROR: Invalid Statseeker API response structure")
                return pd.DataFrame()
        else:
            log_message(f"Statseeker API error: HTTP {response.status_code}")
            return pd.DataFrame()

    except Exception as e:
        log_message(f"Statseeker API connection error: {e}")
        return pd.DataFrame()


def create_smart_hostname_mapping(statseeker_hostname):
    """Create smart hostname variations - optimized for speed."""

    if not statseeker_hostname:
        return []

    variations = [statseeker_hostname]  # Always try original first

    # OPTIMIZATION: Only create 1-2 most likely variations instead of 5
    if '-TSEG' in statseeker_hostname:
        # TrTCHO-TSEG05 -> TrTCHO-SEG05 (most common pattern)
        variations.append(statseeker_hostname.replace('-TSEG', '-SEG'))
    elif '-TSEGS' in statseeker_hostname:
        # TrTCHO-TSEGS01 -> TrTCHO-SEG01
        variations.append(statseeker_hostname.replace('-TSEGS', '-SEG'))

    # Maximum 2 variations to reduce API calls
    return variations[:2]


def fetch_netdb_data_sync(hostname, bearer_token):
    """Fetch NetDB data synchronously for a single hostname."""
    if not bearer_token:
        return create_default_result()

    headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}

    endpoints = [
        ("facts", f"{NETDB_BASE_URL}{hostname}/facts?device_type=extreme_wing"),
        ("interfaces", f"{NETDB_BASE_URL}{hostname}/interfaces?device_type=extreme_wing"),
        ("wireless_clients", f"{NETDB_BASE_URL}{hostname}/wireless-clients?device_type=extreme_wing&rf_domain=self"),
        ("neighbors", f"{NETDB_BASE_URL}{hostname}/neighbors?device_type=extreme_wing")
    ]

    results = {}
    success_count = 0

    for endpoint_name, url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'results' in data:
                    results[endpoint_name] = data['results']
                    success_count += 1
                else:
                    results[endpoint_name] = {}
            else:
                results[endpoint_name] = {}
        except Exception as e:
            results[endpoint_name] = {}
            log_message(f"NetDB endpoint {endpoint_name} error for {hostname}: {str(e)[:50]}")

    if success_count >= 2:  # At least 2 successful endpoints
        ap_details = {
            'netdb_hostname': hostname,
            'found': True,
            'facts': results.get('facts', {}),
            'interfaces': results.get('interfaces', {}),
            'wireless_clients': results.get('wireless_clients', []),
            'neighbors': results.get('neighbors', {})
        }
        return parse_netdb_data(ap_details)

    return create_default_result()


def process_single_ap_sync(ap_row, bearer_token):
    """Process single AP synchronously."""
    statseeker_hostname = ap_row["name"]
    hostname_variations = create_smart_hostname_mapping(statseeker_hostname)

    # Try each hostname variation
    for hostname in hostname_variations:
        result = fetch_netdb_data_sync(hostname, bearer_token)
        if result.get('netdb_responsive'):
            return result

    # No valid hostname found
    return create_default_result()


def process_aps_with_threading(ap_data, bearer_token, max_workers=10):
    """Process APs using ThreadPoolExecutor."""
    log_message(f"Processing {len(ap_data)} APs with {max_workers} threads")

    ap_list = ap_data.to_dict('records')
    netdb_results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_deviceid = {}
        for ap in ap_list:
            future = executor.submit(process_single_ap_sync, ap, bearer_token)
            future_to_deviceid[future] = str(ap['deviceid'])

        # Process completed tasks with progress
        completed = 0
        for future in as_completed(future_to_deviceid):
            deviceid = future_to_deviceid[future]
            try:
                result = future.result()
                netdb_results[deviceid] = result
            except Exception as e:
                log_message(f"Error processing AP {deviceid}: {e}")
                netdb_results[deviceid] = create_default_result()

            completed += 1
            if completed % 10 == 0:
                log_message(f"Processed {completed}/{len(ap_list)} APs ({completed / len(ap_list) * 100:.1f}%)")

    return netdb_results


def parse_netdb_data(ap_details):
    """Parse comprehensive NetDB data - ENHANCED VERSION."""
    try:
        result = {
            'netdb_hostname': ap_details['netdb_hostname'],
            'netdb_responsive': True,
            'serial': 'Unknown',
            'model': 'Unknown',
            'uptime': 'Unknown',
            'interface_count': 0,
            'wireless_ssids': 'N/A',
            'wireless_clients': [],
            'wireless_clients_numbers': 0,
            'vlan_40_ip': 'N/A',
            'vlan1140_ip': 'N/A',
            'connected_switch': 'Unknown',
            'connected_port': 'Unknown',
            # NEW FIELDS
            'vendor': 'Unknown',
            'firmware_version': 'Unknown',
            'operation_mode': 'Unknown',
            'fqdn': 'Unknown',
            'interface_stats': {},
            'switch_management_ip': 'Unknown',
            'switch_platform': 'Unknown',
            'switch_firmware': 'Unknown'
        }

        # Facts parsing - ENHANCED
        facts = ap_details.get('facts', {})
        if facts:
            result.update({
                'serial': facts.get('serial_number', 'Unknown'),
                'model': facts.get('model', 'Unknown'),
                'uptime': facts.get('uptime_string', str(facts.get('uptime', 'Unknown'))),
                'interface_count': len(facts.get('interface_list', [])),
                'vendor': facts.get('vendor', 'Unknown'),
                'firmware_version': facts.get('os_version', 'Unknown'),
                'operation_mode': facts.get('operation_mode', 'Unknown'),
                'fqdn': facts.get('fqdn', 'Unknown')
            })

        # Interface parsing - ENHANCED
        interfaces = ap_details.get('interfaces', {})
        interface_stats = {}

        for int_name, int_data in interfaces.items():
            ip_address = int_data.get('ip_address', '')

            # Collect interface statistics
            interface_stats[int_name] = {
                'is_up': int_data.get('is_up', False),
                'speed': int_data.get('speed', 'Unknown'),
                'duplex': int_data.get('duplex', 'Unknown'),
                'mtu': int_data.get('mtu', 'Unknown'),
                'input_packets': int_data.get('input_packets', 0),
                'output_packets': int_data.get('output_packets', 0),
                'input_errors': int_data.get('input_errors', 0),
                'output_errors': int_data.get('output_errors', 0),
                'mac_address': int_data.get('mac_address', 'Unknown')
            }

            # IP address mapping
            if ip_address:
                if int_name == 'vlan1140':
                    result['vlan1140_ip'] = ip_address
                elif int_name == 'vlan40' or '10.34.' in ip_address:
                    result['vlan_40_ip'] = ip_address

        result['interface_stats'] = interface_stats

        # Wireless clients parsing - ENHANCED
        wireless_clients = ap_details.get('wireless_clients', [])
        if wireless_clients:
            result['wireless_clients_numbers'] = len(wireless_clients)

            client_details = []
            ssids = set()

            for client in wireless_clients:
                client_info = {
                    'hostname': client.get('hostname', 'N/A'),
                    'ip_address': client.get('ip_address', 'N/A'),
                    'mac_address': client.get('mac_address', 'N/A'),
                    'username': client.get('username', 'N/A'),
                    'wlan': client.get('wlan', 'N/A')
                }

                # Add performance metrics if available
                if 'rssi' in client:
                    client_info['rssi'] = client['rssi']
                if 'snr' in client:
                    client_info['snr'] = client['snr']
                if 'data_rate' in client:
                    client_info['data_rate'] = client['data_rate']

                client_details.append(client_info)

                wlan = client.get('wlan')
                if wlan:
                    ssids.add(wlan)

            result['wireless_clients'] = client_details
            result['wireless_ssids'] = ', '.join(list(ssids)) if ssids else 'N/A'

        # Neighbors parsing - ENHANCED
        neighbors = ap_details.get('neighbors', {})
        for interface, neighbor_info in neighbors.items():
            if interface.startswith('ge') and neighbor_info:
                result.update({
                    'connected_switch': neighbor_info.get('hostname', 'Unknown'),
                    'connected_port': neighbor_info.get('remote_port', 'Unknown'),
                    'switch_management_ip': neighbor_info.get('management_ip', 'Unknown'),
                    'switch_platform': neighbor_info.get('platform', 'Unknown'),
                    'switch_firmware': neighbor_info.get('software_version', 'Unknown')[:50]  # Truncate long version
                })
                break

        return result

    except Exception as e:
        log_message(f"NetDB parse error: {str(e)[:100]}")
        result = create_default_result()
        result['netdb_responsive'] = True
        return result

def extract_power_dbm(power_string):
    """'10 dBm (Max)' formatındaki string'den dBm değerini çıkar"""
    try:
        import re
        match = re.search(r'(-?\d+)\s*dBm', str(power_string))
        return int(match.group(1)) if match else 0
    except:
        return 0


def analyze_radio_power(radio_info, client_count):
    """Radio güç seviyelerini analiz et"""
    analysis = {
        'total_radios': len(radio_info),
        'active_radios': len([r for r in radio_info if r['is_active']]),
        'total_power_dbm': sum([r['power_dbm'] for r in radio_info if r['is_active']]),
        'avg_power_dbm': 0,
        'power_efficiency': 'Unknown',
        'frequency_distribution': {},
        'clients_per_radio': 0
    }

    if analysis['active_radios'] > 0:
        analysis['avg_power_dbm'] = analysis['total_power_dbm'] / analysis['active_radios']
        analysis['clients_per_radio'] = client_count / analysis['active_radios'] if analysis['active_radios'] > 0 else 0

        # Power efficiency
        if analysis['avg_power_dbm'] <= 12:
            analysis['power_efficiency'] = 'Optimal'
        elif analysis['avg_power_dbm'] <= 16:
            analysis['power_efficiency'] = 'Good'
        else:
            analysis['power_efficiency'] = 'High'

    # Frequency distribution
    for radio in radio_info:
        freq = radio['frequency_band']
        analysis['frequency_distribution'][freq] = analysis['frequency_distribution'].get(freq, 0) + 1

    return analysis


def fetch_enhanced_wireless_data_v2(hostname, bearer_token):
    """
    Facts, wireless_radios ve neighbors endpoint'lerinden enhanced data topla
    """
    if not bearer_token:
        return {}

    headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}
    base_url = "https://network-api.npe.fedex.com/v1/device/"

    # Çalışan endpoint'ler
    endpoints = [
        ("facts", f"{base_url}{hostname}/facts?device_type=extreme_wing"),
        ("wireless_radios", f"{base_url}{hostname}/wireless-radios?device_type=extreme_wing&rf_domain=self"),
        ("neighbors", f"{base_url}{hostname}/neighbors?device_type=extreme_wing"),
        ("wireless_clients", f"{base_url}{hostname}/wireless-clients?device_type=extreme_wing&rf_domain=self")
    ]

    results = {}

    for endpoint_name, url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'results' in data:
                    results[endpoint_name] = data['results']
        except Exception as e:
            log_message(f"Enhanced endpoint {endpoint_name} error for {hostname}: {str(e)[:50]}")

    return parse_enhanced_data_v2(results, hostname)


def parse_enhanced_data_v2(endpoint_results, hostname):
    """Enhanced endpoint sonuçlarını parse et"""
    enhanced_data = {
        'hostname': hostname,
        'radio_info': [],
        'client_radio_mapping': [],
        'device_facts': {},
        'neighbor_info': {},
        'signal_analysis': {}
    }

    try:
        # Facts parsing
        facts = endpoint_results.get('facts', {})
        if facts:
            enhanced_data['device_facts'] = {
                'model': facts.get('model', 'Unknown'),
                'os_version': facts.get('os_version', 'Unknown'),
                'uptime_seconds': facts.get('uptime', 0),
                'uptime_string': facts.get('uptime_string', 'Unknown'),
                'operation_mode': facts.get('operation_mode', 'Unknown'),
                'interface_count': len(facts.get('interface_list', []))
            }

        # Wireless Radios parsing - Radio güçleri ve kanalları
        radios = endpoint_results.get('wireless_radios', [])
        for radio in radios:
            radio_info = {
                'radio_id': radio.get('radio', 'Unknown'),
                'mac_address': radio.get('mac_address', 'Unknown'),
                'frequency': radio.get('rf_mode', 'Unknown'),
                'state': radio.get('state', 'Unknown'),
                'channel': radio.get('channel', 'Unknown'),
                'power_dbm': extract_power_dbm(radio.get('power', '0 dBm')),
                'power_raw': radio.get('power', 'Unknown'),
                'is_active': 'On' in radio.get('state', ''),
                'frequency_band': '2.4GHz' if '2.4GHz' in radio.get('rf_mode', '') else '5GHz' if '5GHz' in radio.get(
                    'rf_mode', '') else 'Other'
            }
            enhanced_data['radio_info'].append(radio_info)

        # Wireless Clients + Radio Mapping - BU SINYAL GÜÇ BİLGİSİ
        clients = endpoint_results.get('wireless_clients', [])
        for client in clients:
            # Client'i hangi radio'ya bağlı olduğunu bul
            client_radio = client.get('radio', 'Unknown')
            radio_type = client.get('radio_type', 'Unknown')

            # Radio bilgisinden güç seviyesini çek
            radio_power = None
            for radio in enhanced_data['radio_info']:
                if client_radio in radio['radio_id']:
                    radio_power = radio['power_dbm']
                    break

            client_info = {
                'hostname': client.get('hostname', 'Unknown'),
                'mac_address': client.get('mac_address', 'Unknown'),
                'ip_address': client.get('ip_address', 'Unknown'),
                'username': client.get('username', 'Unknown'),
                'radio_id': client_radio,
                'radio_type': radio_type,
                'radio_power_dbm': radio_power,  # BU SINYAL GÜÇ BİLGİSİ
                'vlan_id': client.get('vlan_id', 0),
                'activity': client.get('activity', 'Unknown'),
                'state': client.get('state', 'Unknown'),
                'vendor': client.get('vendor', 'Unknown'),
                'connected_since': datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%d-%m-%Y %H:%M:%S')
            }
            enhanced_data['client_radio_mapping'].append(client_info)

        # Neighbor info - Switch bağlantısı
        neighbors = endpoint_results.get('neighbors', {})
        if neighbors:
            for interface, neighbor_data in neighbors.items():
                enhanced_data['neighbor_info'] = {
                    'local_interface': interface,
                    'switch_hostname': neighbor_data.get('hostname', 'Unknown'),
                    'switch_ip': neighbor_data.get('management_ip', 'Unknown'),
                    'switch_platform': neighbor_data.get('platform', 'Unknown'),
                    'switch_port': neighbor_data.get('remote_port', 'Unknown'),
                    'switch_software': neighbor_data.get('software_version', 'Unknown')[:100]
                }
                break

        # Signal Analysis - Radio güçlerinden analiz
        enhanced_data['signal_analysis'] = analyze_radio_power(enhanced_data['radio_info'], len(clients))

    except Exception as e:
        log_message(f"Enhanced parse error for {hostname}: {str(e)[:100]}")

    return enhanced_data




def calculate_signal_quality(rssi):
    """
    RSSI değerine göre sinyal kalitesi hesapla
    """
    if rssi >= -30:
        return "Excellent"
    elif rssi >= -50:
        return "Good"
    elif rssi >= -70:
        return "Fair"
    elif rssi >= -90:
        return "Poor"
    else:
        return "Very Poor"


def integrate_enhanced_wireless_data(ap_data, bearer_token, max_workers=5):
    """
    Mevcut AP verilerine enhanced wireless data ekle
    """
    log_message("=== ENHANCED WIRELESS DATA COLLECTION STARTED ===")

    enhanced_results = {}
    ap_list = ap_data.to_dict('records')

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_hostname = {}

        for ap in ap_list[:10]:  # İlk 10 AP için test - sonra tümünü çalıştırabilirsin
            hostname_variations = create_smart_hostname_mapping(ap['name'])
            for hostname in hostname_variations:
                future = executor.submit(fetch_enhanced_wireless_data_v2, hostname, bearer_token)
                future_to_hostname[future] = {
                    'deviceid': str(ap['deviceid']),
                    'hostname': hostname,
                    'original_name': ap['name']
                }

        completed = 0
        for future in as_completed(future_to_hostname):
            ap_info = future_to_hostname[future]
            try:
                enhanced_data = future.result()
                if enhanced_data:  # Veri varsa kaydet
                    enhanced_results[ap_info['deviceid']] = enhanced_data
                    log_message(f"Enhanced data collected for {ap_info['original_name']}")
            except Exception as e:
                log_message(f"Enhanced data error for {ap_info['original_name']}: {e}")

            completed += 1
            if completed % 5 == 0:
                log_message(f"Enhanced data processed: {completed}/{len(future_to_hostname)}")

    log_message(f"=== ENHANCED WIRELESS DATA COLLECTION COMPLETED: {len(enhanced_results)} APs ===")
    return enhanced_results


def create_enhanced_wireless_report_v2(enhanced_data_dict):
    """Enhanced wireless data'dan comprehensive rapor oluştur"""
    report_file = 'D:/INTRANET/Netinfo/Data/enhanced_wireless_report_v2.json'

    # Summary statistics
    summary = {
        'last_updated': datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%d-%m-%Y %H:%M:%S'),
        'total_aps': len(enhanced_data_dict),
        'total_active_radios': 0,
        'total_clients_mapped': 0,
        'avg_power_dbm': 0,
        'frequency_bands': {'2.4GHz': 0, '5GHz': 0, 'Other': 0},
        'power_efficiency_distribution': {'Optimal': 0, 'Good': 0, 'High': 0},
        'top_client_density_aps': []
    }

    all_powers = []
    client_density_list = []

    for deviceid, data in enhanced_data_dict.items():
        if 'signal_analysis' in data:
            analysis = data['signal_analysis']
            summary['total_active_radios'] += analysis.get('active_radios', 0)
            summary['total_clients_mapped'] += len(data.get('client_radio_mapping', []))

            if analysis.get('avg_power_dbm', 0) > 0:
                all_powers.append(analysis['avg_power_dbm'])

            # Power efficiency
            efficiency = analysis.get('power_efficiency', 'Unknown')
            if efficiency in summary['power_efficiency_distribution']:
                summary['power_efficiency_distribution'][efficiency] += 1

            # Frequency bands
            freq_dist = analysis.get('frequency_distribution', {})
            for freq, count in freq_dist.items():
                if freq in summary['frequency_bands']:
                    summary['frequency_bands'][freq] += count

            # Client density
            client_count = len(data.get('client_radio_mapping', []))
            if client_count > 0:
                client_density_list.append({
                    'hostname': data.get('hostname', 'Unknown'),
                    'client_count': client_count,
                    'avg_power': analysis.get('avg_power_dbm', 0),
                    'active_radios': analysis.get('active_radios', 0)
                })

    # Average power
    summary['avg_power_dbm'] = sum(all_powers) / len(all_powers) if all_powers else 0

    # Top client density
    summary['top_client_density_aps'] = sorted(client_density_list, key=lambda x: x['client_count'], reverse=True)[:10]

    # Full report
    report_data = {
        'summary': summary,
        'detailed_ap_data': enhanced_data_dict
    }

    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        log_message(f"Enhanced wireless report v2 saved: {report_file}")

        # Console summary
        log_message("=== ENHANCED WIRELESS REPORT V2 ===")
        log_message(f"Total APs: {summary['total_aps']}")
        log_message(f"Active Radios: {summary['total_active_radios']}")
        log_message(f"Clients Mapped: {summary['total_clients_mapped']}")
        log_message(f"Avg Power: {summary['avg_power_dbm']:.1f} dBm")
        log_message(f"Frequency Bands: {summary['frequency_bands']}")
        log_message(f"Power Efficiency: {summary['power_efficiency_distribution']}")

        if summary['top_client_density_aps']:
            log_message("Top Client Density APs:")
            for ap in summary['top_client_density_aps'][:5]:
                log_message(f"  {ap['hostname']}: {ap['client_count']} clients, {ap['avg_power']:.1f}dBm")

    except Exception as e:
        log_message(f"Enhanced report save error: {e}")


def integrate_enhanced_wireless_data_v2(ap_data, bearer_token, max_workers=8):
    """V2 enhanced wireless data collection - çalışan endpoint'lerle"""
    log_message("=== ENHANCED WIRELESS DATA V2 COLLECTION STARTED ===")

    enhanced_results = {}
    ap_list = ap_data.to_dict('records')

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_info = {}


        for ap in ap_list:
            hostname_variations = create_smart_hostname_mapping(ap['name'])
            for hostname in hostname_variations:
                future = executor.submit(fetch_enhanced_wireless_data_v2, hostname, bearer_token)
                future_to_info[future] = {
                    'deviceid': str(ap['deviceid']),
                    'hostname': hostname,
                    'original_name': ap['name']
                }

        completed = 0
        for future in as_completed(future_to_info):
            ap_info = future_to_info[future]
            try:
                enhanced_data = future.result()
                if enhanced_data and (
                        enhanced_data.get('radio_info') or
                        enhanced_data.get('client_radio_mapping') or
                        enhanced_data.get('device_facts')
                ):
                    enhanced_results[ap_info['deviceid']] = enhanced_data
                    log_message(f"Enhanced data: {ap_info['original_name']}")

            except Exception as e:
                log_message(f"Enhanced error: {ap_info['original_name']} - {e}")

            completed += 1
            if completed % 5 == 0:
                log_message(f"Progress: {completed}/{len(future_to_info)}")

    log_message(f"=== V2 COLLECTION COMPLETED: {len(enhanced_results)} successful APs ===")

    if enhanced_results:
        create_enhanced_wireless_report_v2(enhanced_results)

    return enhanced_results

def save_enhanced_wireless_report(enhanced_data):
    """
    Enhanced wireless verilerini JSON dosyasına kaydet
    """
    enhanced_file = 'D:/INTRANET/Netinfo/Data/enhanced_wireless_data.json'

    try:
        # Summary istatistikleri hazırla
        summary = {
            'last_updated': datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%d-%m-%Y %H:%M:%S'),
            'total_aps_with_enhanced_data': len(enhanced_data),
            'total_clients_with_signal_data': 0,
            'total_connection_events': 0,
            'total_roaming_events': 0,
            'signal_quality_distribution': {'Excellent': 0, 'Good': 0, 'Fair': 0, 'Poor': 0, 'Very Poor': 0}
        }

        for deviceid, data in enhanced_data.items():
            summary['total_clients_with_signal_data'] += len(data.get('client_signal_data', []))
            summary['total_connection_events'] += len(data.get('connection_events', []))
            summary['total_roaming_events'] += len(data.get('roaming_history', []))

            # Signal quality dağılımı
            for client in data.get('client_signal_data', []):
                quality = client.get('signal_quality', 'Unknown')
                if quality in summary['signal_quality_distribution']:
                    summary['signal_quality_distribution'][quality] += 1

        # Ana veri + özet
        output_data = {
            'summary': summary,
            'enhanced_wireless_data': enhanced_data
        }

        with open(enhanced_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        log_message(f"Enhanced wireless data saved: {enhanced_file}")

        # Özet raporu logla
        log_message("=== ENHANCED WIRELESS SUMMARY ===")
        log_message(f"APs with enhanced data: {summary['total_aps_with_enhanced_data']}")
        log_message(f"Clients with signal data: {summary['total_clients_with_signal_data']}")
        log_message(f"Connection events: {summary['total_connection_events']}")
        log_message(f"Roaming events: {summary['total_roaming_events']}")
        log_message(f"Signal quality: {summary['signal_quality_distribution']}")

    except Exception as e:
        log_message(f"Enhanced wireless data save error: {e}")

def create_default_result():
    """Create default result for when NetDB is not available."""
    return {
        'netdb_hostname': 'N/A',
        'netdb_responsive': False,
        'serial': 'Unknown',
        'model': 'Extreme Access Point',
        'uptime': 'Unknown',
        'interface_count': 0,
        'wireless_ssids': 'N/A',
        'wireless_clients': [],
        'wireless_clients_numbers': 0,
        'vlan_40_ip': 'N/A',
        'vlan1140_ip': 'N/A',
        'connected_switch': 'Unknown',
        'connected_port': 'Unknown',
        # NEW DEFAULT VALUES
        'vendor': 'Unknown',
        'firmware_version': 'Unknown',
        'operation_mode': 'Unknown',
        'fqdn': 'Unknown',
        'interface_stats': {},
        'switch_management_ip': 'Unknown',
        'switch_platform': 'Unknown',
        'switch_firmware': 'Unknown'
    }


def extract_ap_location(hostname, deviceid=None):
    """Extract location from AP hostname."""
    if not hostname or not isinstance(hostname, str):
        log_message(f"WARN: Invalid hostname ({hostname}) for deviceid: {deviceid}")
        return 'Unknown'

    try:
        patterns = [
            r'Tr([A-Za-z0-9]+?)(?:-?TSEG)',  # TrTOZN-TSEGS01 -> TOZN
            r'Tr([A-Za-z0-9]+?)(?=SEG)',  # TrTOZNSEG01 -> TOZN
            r'TrT([A-Za-z0-9]+?)(?:-?SEG)',  # TrTADA-TSEG02 -> ADA
            r'Tr([A-Za-z]+)T.*SEG',  # TrISTTSEG -> IST
            r'Tr([A-Za-z0-9]{3,4}).*SEG'  # Generic pattern
        ]

        for pattern in patterns:
            match = re.search(pattern, hostname, re.IGNORECASE)
            if match:
                location = match.group(1).upper()
                return location

        return 'Unknown'
    except Exception as e:
        log_message(f"ERROR: Location extraction error. hostname={hostname}, deviceid={deviceid} -> {e}")
        return 'Unknown'


def load_uuid_mapping():
    """Load UUID mapping from existing UUID_Pool.json."""
    uuid_file = 'D:/INTRANET/Netinfo/Data/UUID_Pool.json'

    if not os.path.exists(uuid_file):
        log_message(f"UUID file not found: {uuid_file}")
        return {}, []

    try:
        with open(uuid_file, 'r', encoding='utf-8') as f:
            uuid_data = json.load(f)

        uuid_mapping = uuid_data.get("deviceid_uuid_mapping", {})
        available_uuids = uuid_data.get("available_uuids", [])

        log_message(f"UUID Mapping loaded: {len(uuid_mapping)} devices, {len(available_uuids)} available UUIDs")
        return uuid_mapping, available_uuids
    except json.JSONDecodeError:
        log_message(f"ERROR: UUID_Pool.json is corrupted!")
        return {}, []
    except Exception as e:
        log_message(f"ERROR: UUID loading error: {e}")
        return {}, []


def save_hourly_client_stats(updated_aps):
    """Saatlik client istatistiklerini zenginleştirilmiş formatta kaydet"""
    try:
        now = datetime.now(pytz.timezone("Europe/Istanbul"))
        hour_key = now.strftime('%Y-%m-%d_%H')

        # Detaylı istatistikleri hesapla
        total_clients = sum(ap.get('wireless_clients_numbers', 0) for ap in updated_aps)
        online_aps = len([ap for ap in updated_aps if ap.get('is_up', True)])
        total_aps = len(updated_aps)

        # SSID dağılımı
        ssid_breakdown = {}
        location_breakdown = {}
        for ap in updated_aps:
            # Lokasyon breakdown
            location = ap.get('city', 'Unknown')
            if location not in location_breakdown:
                location_breakdown[location] = {'aps': 0, 'clients': 0}
            location_breakdown[location]['aps'] += 1
            location_breakdown[location]['clients'] += ap.get('wireless_clients_numbers', 0)

            # SSID breakdown
            for client in ap.get('wireless_clients', []):
                ssid = client.get('wlan', 'NULL')
                ssid_breakdown[ssid] = ssid_breakdown.get(ssid, 0) + 1

        # En yoğun AP'ler
        top_aps = sorted(updated_aps,
                         key=lambda x: x.get('wireless_clients_numbers', 0),
                         reverse=True)[:5]

        # Yeni veri yapısı
        hour_data = {
            'total_clients': total_clients,
            'total_aps': total_aps,
            'online_aps': online_aps,
            'offline_aps': total_aps - online_aps,
            'avg_clients_per_ap': round(total_clients / total_aps, 1) if total_aps > 0 else 0,
            'timestamp': now.isoformat(),
            'top_aps': [
                {
                    'hostname': ap.get('hostname', 'Unknown'),
                    'clients': ap.get('wireless_clients_numbers', 0),
                    'location': ap.get('city', 'Unknown')
                }
                for ap in top_aps
            ],
            'ssid_breakdown': dict(sorted(ssid_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]),
            'location_breakdown': dict(
                sorted(location_breakdown.items(), key=lambda x: x[1]['clients'], reverse=True)[:10]),
            'uptime_percentage': round((online_aps / total_aps) * 100, 1) if total_aps > 0 else 0
        }

        stats_file = 'D:/INTRANET/Netinfo/Data/hourly_client_stats.json'

        # Mevcut stats'ı yükle
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                hourly_stats = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            hourly_stats = {}

        # Peak client sayısına göre güncelle veya yeni ekle
        if hour_key in hourly_stats:
            existing_data = hourly_stats[hour_key]
            if isinstance(existing_data, int):
                # Eski format, yeni formata dönüştür
                if total_clients >= existing_data:
                    hourly_stats[hour_key] = hour_data
            else:
                # Yeni format, peak değere göre güncelle
                if total_clients >= existing_data.get('total_clients', 0):
                    hourly_stats[hour_key] = hour_data
        else:
            hourly_stats[hour_key] = hour_data

        # Son 48 saati sakla (daha fazla tarihçe için)
        cutoff_time = now - timedelta(hours=48)
        hourly_stats = {
            k: v for k, v in hourly_stats.items()
            if datetime.strptime(k, '%Y-%m-%d_%H') > cutoff_time.replace(tzinfo=None)
        }

        # Kaydet
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(hourly_stats, f, indent=2, ensure_ascii=False)

        log_message(f"Enhanced hourly stats saved: {hour_key} = {total_clients} clients (peak)")

    except Exception as e:
        log_message(f"Error saving enhanced hourly stats: {e}")

def station_info():
    """Load station information with fallback mapping."""
    station_file = 'D:/INTRANET/Netinfo/Data/station-info.json'

    fallback_mapping = {
        'IST': 'Istanbul', 'IZM': 'Izmir', 'ANK': 'Ankara', 'OZN': 'Serifali',
        'ADA': 'Adana', 'ASR': 'Kayseri', 'KYA': 'Konya', 'DNZ': 'Denizli',
        'TOZN': 'Serifali', 'TBL5': 'Hadimkoy', 'TANK': 'Ankara', 'TASR': 'Kayseri',
        'TAYT': 'Antalya', 'TIZM': 'Izmir', 'TKYA': 'Konya', 'TCHO': 'Istanbul HQ',
        'TIST': 'Gunesli', 'TGZT': 'Gaziantep', 'TDNZ': 'Denizli', 'TAJIA': 'Balikesir',
        'TADA': 'Adana', 'TCC8': 'Catalca', 'AJIA': 'Balikesir', 'GZT': 'Gaziantep',
        'BTZ': 'Bursa', 'TBTZ': 'Bursa', 'AOE': 'Eskisehir', 'TAOE': 'Eskisehir', 'CC8': 'Catalca', 'CHO': 'Istanbul HQ', 'SAW': 'SAW', 'TSAW': 'SAW', 'ISTRT2': 'Istanbul Airport', 'ISTRT': 'Istanbul Airport'
    }

    if not os.path.exists(station_file):
        return fallback_mapping

    try:
        with open(station_file, 'r', encoding='utf-8') as f:
            station_data = json.load(f)

        code_mapping = fallback_mapping.copy()
        for entry in station_data:
            if isinstance(entry, dict):
                town = entry.get('town', 'Unknown')
                if 'code' in entry:
                    code_mapping[entry['code']] = town
                if 'alternate_code' in entry:
                    code_mapping[entry['alternate_code']] = town

        return code_mapping
    except Exception as e:
        log_message(f"Station info loading error: {e}")
        return fallback_mapping


def load_main_data():
    """Load switch port connection data from main_data.json."""
    main_data_file = 'D:/INTRANET/Netinfo/Data/main_data.json'
    if not os.path.exists(main_data_file):
        return {}

    try:
        with open(main_data_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)

        switch_connections = {}
        data_section = main_data.get('data', {})

        for switch_name, switch_data in data_section.items():
            if isinstance(switch_data, dict) and 'ports' in switch_data:
                for port in switch_data['ports']:
                    if isinstance(port, dict):
                        neighbor_hostname = port.get('neighbor_hostname')
                        if (isinstance(neighbor_hostname, str) and
                                neighbor_hostname != 'N/A' and
                                'SEG' in neighbor_hostname):
                            switch_connections[neighbor_hostname] = {
                                'connected_switch': switch_name,
                                'connected_port': port.get('interface_name', 'N/A'),
                                'neighbor_port': port.get('neighbor_port', 'N/A'),
                                'link_status': port.get('link_status', 'unknown'),
                                'is_up': port.get('is_up', False)
                            }

        log_message(f"Switch connections loaded: {len(switch_connections)} AP connections found")
        return switch_connections
    except Exception as e:
        log_message(f"main_data.json loading error: {e}")
        return {}


async def process_aps_in_batches(ap_data, bearer_token, batch_size=10):
    """Process APs in batches asynchronously - DEPRECATED, using threading now."""
    # This function is kept for backward compatibility but not used
    return {}


def update_ap_data():
    """Main function to collect and process AP data - USING THREADING."""
    json_file = 'D:/INTRANET/Netinfo/Data/access_point_inventory.json'

    log_message("=== ACCESS POINT DATA COLLECTION STARTED (THREADING) ===")

    # Load previous data
    previous_data = {}
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                previous_data = {str(d['deviceid']): d for d in json.load(f)}
            log_message(f"Previous data loaded: {len(previous_data)} records")
        except json.JSONDecodeError:
            log_message("ERROR: AP JSON file corrupted, starting fresh!")
            previous_data = {}

    # Load UUID mapping and other data
    uuid_mapping, available_uuids = load_uuid_mapping()
    switch_connections = load_main_data()

    # Get NetDB token
    bearer_token = get_netdb_bearer_token()
    if bearer_token:
        log_message("NetDB token available - will fetch comprehensive AP data")
    else:
        log_message("NetDB token not available - will use Statseeker data only")

    # Fetch Statseeker data
    log_message("Fetching AP device data from Statseeker...")
    ap_data = fetch_statseeker_ap_data()

    if ap_data.empty:
        log_message("ERROR: No SEG devices found in Statseeker!")
        return

    log_message(f"Statseeker: {len(ap_data)} SEG devices found")

    # Add hostname and location columns
    ap_data['hostname'] = ap_data['name']
    ap_data['location'] = ap_data.apply(
        lambda row: extract_ap_location(row['hostname'], row['deviceid']),
        axis=1
    )

    station_mapping = station_info()
    ap_data['city'] = ap_data['location'].map(lambda x: station_mapping.get(x, 'Unknown'))

    # Assign UUIDs
    log_message("UUID assignment started...")
    for index, row in ap_data.iterrows():
        deviceid = str(row["deviceid"])
        if deviceid not in uuid_mapping:
            if available_uuids:
                assigned_uuid = available_uuids.pop(0)
                uuid_mapping[deviceid] = assigned_uuid
            else:
                assigned_uuid = "UUID_NOT_ASSIGNED"
            ap_data.at[index, 'uuid'] = assigned_uuid
        else:
            ap_data.at[index, 'uuid'] = uuid_mapping[deviceid]

    # Process APs with NetDB data using threading
    netdb_results = {}
    enhanced_results = {}  # BUNU EKLE

    if bearer_token:
        log_message("Starting threaded processing...")
        processing_start = time.time()

        # Use threading instead of async
        netdb_results = process_aps_with_threading(ap_data, bearer_token, max_workers=15)

        # ENHANCED DATA COLLECTION - BUNU EKLE
        log_message("Starting enhanced wireless data collection...")
        enhanced_results = integrate_enhanced_wireless_data_v2(ap_data, bearer_token, max_workers=8)

        processing_time = time.time() - processing_start
        responsive_count = sum(1 for r in netdb_results.values() if r.get('netdb_responsive'))
        log_message(
            f"NetDB processing completed in {processing_time:.1f}s ({len(ap_data) / processing_time:.1f} APs/sec)")
        log_message(
            f"NetDB responsive APs: {responsive_count}/{len(ap_data)} ({responsive_count / len(ap_data) * 100:.1f}%)")
    else:
        log_message("Skipping NetDB processing - no token available")
        for _, ap in ap_data.iterrows():
            netdb_results[str(ap['deviceid'])] = create_default_result()

    # Create final AP records
    updated_aps = []
    now = datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%d-%m-%Y %H:%M:%S')

    log_message("Creating final AP records...")

    for _, ap in ap_data.iterrows():
        deviceid = str(ap["deviceid"])
        hostname = ap.get("hostname", ap.get("name", ""))

        # Get NetDB data
        netdb_data = netdb_results.get(deviceid, create_default_result())

        # ENHANCED DATA'YI AL - BUNU EKLE
        enhanced_data = enhanced_results.get(deviceid, {})

        # Determine status
        current_status = "up"  # If in Statseeker, it's up
        previous_status = previous_data.get(deviceid, {}).get("ping_state", current_status)

        # Get switch connection info
        switch_info = switch_connections.get(hostname, {})
        connected_switch = netdb_data.get('connected_switch', 'Unknown')
        connected_port = netdb_data.get('connected_port', 'Unknown')

        if connected_switch == 'Unknown':
            connected_switch = switch_info.get('connected_switch', 'Unknown')
            connected_port = switch_info.get('connected_port', 'Unknown')

        # Create final AP record
        updated_ap = {
            "id": ap["deviceid"],
            "deviceid": ap["deviceid"],
            "hostname": hostname,
            "ipaddress": ap.get("ipaddress", ""),
            "ping_state": current_status,
            "serial": netdb_data.get('serial', 'Unknown'),
            "model": netdb_data.get('model', 'Extreme Access Point'),
            "device_type": "Access Point",
            "location": ap.get("location", "Unknown"),
            "city": ap.get("city", "Unknown"),
            "uuid": ap.get("uuid", "UNKNOWN"),
            "data_source": "Statseeker + NetDB" if netdb_data.get('netdb_responsive') else "Statseeker",
            "interface_count": netdb_data.get('interface_count', 0),
            "wireless_ssids": netdb_data.get('wireless_ssids', 'N/A'),
            "wireless_clients": netdb_data.get('wireless_clients', []),
            "wireless_clients_numbers": netdb_data.get('wireless_clients_numbers', 0),
            "vlan_40_ip": netdb_data.get('vlan_40_ip', 'N/A'),
            "vlan1140_ip": netdb_data.get('vlan1140_ip', 'N/A'),
            "uptime": netdb_data.get('uptime', 'Unknown'),
            "connected_switch": connected_switch,
            "connected_port": connected_port,
            "neighbor_port": switch_info.get('neighbor_port', 'N/A'),
            "link_status": switch_info.get('link_status', 'unknown'),
            "is_up": switch_info.get('is_up', True),
            "last_updated": now,
            "notes": "",
            # ENHANCED WIRELESS DATA EKLE - BUNU EKLE
            "enhanced_wireless": enhanced_data
        }

        updated_aps.append(updated_ap)

    # Save data
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(updated_aps, f, indent=2, ensure_ascii=False)

        log_message(f"AP inventory saved: {len(updated_aps)} records")

        # Update UUID mapping file
        uuid_data = {
            "deviceid_uuid_mapping": uuid_mapping,
            "available_uuids": available_uuids,
            "last_updated": now
        }

        uuid_file = 'D:/INTRANET/Netinfo/Data/UUID_Pool.json'
        with open(uuid_file, 'w', encoding='utf-8') as f:
            json.dump(uuid_data, f, indent=2)

        log_message("UUID mapping updated and saved")

        # Generate summary statistics
        responsive_count = sum(1 for ap in updated_aps if ap.get('data_source') == 'Statseeker + NetDB')
        total_clients = sum(ap.get('wireless_clients_numbers', 0) for ap in updated_aps)
        save_hourly_client_stats(updated_aps)

        # Location summary
        location_stats = {}
        for ap in updated_aps:
            location = ap.get('city', 'Unknown')
            if location not in location_stats:
                location_stats[location] = {'count': 0, 'clients': 0}
            location_stats[location]['count'] += 1
            location_stats[location]['clients'] += ap.get('wireless_clients_numbers', 0)

        log_message(f"=== SUMMARY STATISTICS ===")
        log_message(f"Total APs processed: {len(updated_aps)}")
        log_message(f"NetDB responsive APs: {responsive_count}")
        log_message(f"Total wireless clients: {total_clients}")
        log_message(f"Average clients per AP: {total_clients / len(updated_aps):.1f}")

        log_message("=== LOCATION BREAKDOWN ===")
        for location, stats in sorted(location_stats.items()):
            log_message(f"{location}: {stats['count']} APs, {stats['clients']} clients")

        # Performance summary
        total_time = time.time() - start_time
        log_message(f"=== PERFORMANCE SUMMARY ===")
        log_message(f"Total execution time: {total_time:.1f} seconds")
        log_message(f"Processing rate: {len(updated_aps) / total_time:.2f} APs/second")

        log_message("=== ACCESS POINT INVENTORY UPDATE COMPLETED ===")

    except Exception as e:
        log_message(f"ERROR: Failed to save AP inventory: {e}")
        raise


def generate_ap_report():
    """Generate a comprehensive AP status report."""
    json_file = 'D:/INTRANET/Netinfo/Data/access_point_inventory.json'

    if not os.path.exists(json_file):
        log_message("ERROR: AP inventory file not found!")
        return

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            ap_data = json.load(f)

        log_message("=== ACCESS POINT STATUS REPORT ===")

        # Basic statistics
        total_aps = len(ap_data)
        responsive_aps = sum(1 for ap in ap_data if ap.get('data_source') == 'Statseeker + NetDB')
        total_clients = sum(ap.get('wireless_clients_numbers', 0) for ap in ap_data)

        log_message(f"Total Access Points: {total_aps}")
        log_message(f"NetDB Responsive: {responsive_aps} ({responsive_aps / total_aps * 100:.1f}%)")
        log_message(f"Total Wireless Clients: {total_clients}")
        log_message(f"Average Clients per AP: {total_clients / total_aps:.1f}")

        # Top locations by AP count
        location_counts = {}
        for ap in ap_data:
            city = ap.get('city', 'Unknown')
            location_counts[city] = location_counts.get(city, 0) + 1

        log_message("\n=== TOP LOCATIONS BY AP COUNT ===")
        for city, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            log_message(f"{city}: {count} APs")

        # APs with most clients
        high_usage_aps = sorted(ap_data, key=lambda x: x.get('wireless_clients_numbers', 0), reverse=True)[:10]

        log_message("\n=== TOP 10 APs BY CLIENT COUNT ===")
        for ap in high_usage_aps:
            log_message(
                f"{ap.get('hostname', 'Unknown')}: {ap.get('wireless_clients_numbers', 0)} clients - {ap.get('city', 'Unknown')}")

        # Non-responsive APs
        non_responsive = [ap for ap in ap_data if ap.get('data_source') != 'Statseeker + NetDB']

        if non_responsive:
            log_message(f"\n=== NON-RESPONSIVE APs ({len(non_responsive)}) ===")
            for ap in non_responsive[:20]:  # Show first 20
                log_message(f"{ap.get('hostname', 'Unknown')} - {ap.get('city', 'Unknown')}")

        # Model distribution
        model_counts = {}
        for ap in ap_data:
            model = ap.get('model', 'Unknown')
            model_counts[model] = model_counts.get(model, 0) + 1

        log_message("\n=== AP MODEL DISTRIBUTION ===")
        for model, count in sorted(model_counts.items(), key=lambda x: x[1], reverse=True):
            log_message(f"{model}: {count} units ({count / total_aps * 100:.1f}%)")

        log_message("=== REPORT GENERATION COMPLETED ===")

    except Exception as e:
        log_message(f"ERROR: Failed to generate report: {e}")


def cleanup_old_logs():
    """Clean up log files older than 30 days."""
    try:
        import glob
        from datetime import timedelta

        log_files = glob.glob(os.path.join(log_directory, "access_point_inventory_*.log"))
        cutoff_date = datetime.now() - timedelta(days=30)

        cleaned_count = 0
        for log_file in log_files:
            try:
                file_date = datetime.fromtimestamp(os.path.getctime(log_file))
                if file_date < cutoff_date:
                    os.remove(log_file)
                    cleaned_count += 1
            except Exception as e:
                log_message(f"Error cleaning log file {log_file}: {e}")

        if cleaned_count > 0:
            log_message(f"Cleaned up {cleaned_count} old log files")

    except Exception as e:
        log_message(f"Error during log cleanup: {e}")


# Ana fonksiyonunda şunu ekle:
def main():
    try:
        cleanup_old_logs()
        update_ap_data()  # Bu artık enhanced data'yı da içeriyor
        generate_ap_report()

    except KeyboardInterrupt:
        log_message("Script interrupted by user")
    except Exception as e:
        log_message(f"CRITICAL ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
