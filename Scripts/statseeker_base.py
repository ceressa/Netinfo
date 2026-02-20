import uuid

import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import json
import urllib3
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding='utf-8')


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SSL_VERIFY = os.environ.get("SSL_CERT_PATH", True)


# API connection details
base_url = 'https://statseeker.emea.fedex.com/api/v2.1/'
user = os.environ.get("STATSEEKER_USERNAME")
password = os.environ.get("STATSEEKER_PASSWORD")

fields = {
    'device': 'id,deviceid,hostname,ipaddress,ping_state',
    'inventory': 'deviceid,serial,model'
}


# URLs
urls = {
    name: f"{base_url}cdt_{name}?fields={fields[name]}&groups=NOC-Turkey&links=none&limit=10000"
    for name in fields
}

# Log ayarları
log_directory = "D:/INTRANET/Netinfo/Logs/Latest_Logs"
os.makedirs(log_directory, exist_ok=True)

log_start_date = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y%m%d")
log_file_path = os.path.join(log_directory, f"network_device_inventory_{log_start_date}.log")

STATUS_LOG_FILE = "D:/INTRANET/Netinfo/Logs/Latest_Logs/device_status_changes.json"
ARCHIVE_FOLDER = "D:/INTRANET/Netinfo/Logs/Archived_Logs"
uuid_file = 'D:/INTRANET/Netinfo/Data/UUID_Pool.json'



def reload_uuid_mapping():
    """ UUID dosyasını her çağrıda yeniden yükler ve güncellenmiş veriyi döndürür """
    if not os.path.exists(uuid_file):
        log_message(f"🔴 ERROR: UUID Mapping dosyası bulunamadı: {uuid_file}")
        return {}, []

    try:
        with open(uuid_file, 'r', encoding='utf-8') as f:
            uuid_data = json.load(f)

        uuid_mapping = uuid_data.get("deviceid_uuid_mapping", {})
        available_uuids = uuid_data.get("available_uuids", [])

        log_message(f"✅ UUID Mapping Yüklendi: {len(uuid_mapping)} cihaz, {len(available_uuids)} boş UUID")
        return uuid_mapping, available_uuids
    except json.JSONDecodeError:
        log_message(f"🔴 ERROR: UUID_Pool.json bozuk, yüklenemedi!")
        return {}, []
    except Exception as e:
        log_message(f"🔴 ERROR: UUID Mapping yüklenirken hata oluştu: {e}")
        return {}, []


def log_message(message):
    """Write log messages to a file (UTF-8 encoded to prevent encoding errors)."""
    global log_start_date
    current_date = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y%m%d')

    if current_date != log_start_date:
        log_start_date = current_date
        global log_file_path
        log_file_path = os.path.join(log_directory, f"network_device_inventory_{current_date}.log")

    timestamp = datetime.now(pytz.timezone('Europe/Istanbul')).strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"{timestamp} - {message}\n"

    try:
        with open(log_file_path, 'a', encoding='utf-8') as log_file:
            log_file.write(log_entry)
    except Exception as e:
        print(f"🔴 HATA: Log dosyasına yazılırken hata oluştu: {e}")


def log_status_change(deviceid, hostname, old_status, new_status, serial):
    """Cihazın durum değişikliklerini loglar ve her kayda benzersiz bir log_id ekler."""

    # 📂 JSON dosyasını oku (varsa)
    if os.path.exists(STATUS_LOG_FILE):
        try:
            with open(STATUS_LOG_FILE, 'r', encoding='utf-8') as f:
                status_logs = json.load(f)
                if not isinstance(status_logs, list):
                    status_logs = []
        except json.JSONDecodeError:
            status_logs = []
    else:
        status_logs = []

    # ⏳ **Son 24 saat içinde aynı cihazın son kaydını bul**
    now = datetime.now(pytz.timezone("Europe/Istanbul"))
    last_24_hours = now - timedelta(hours=24)

    last_entry = None
    filtered_logs = [log for log in status_logs if log["deviceid"] == deviceid]

    if filtered_logs:
        last_entry = max(filtered_logs, key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%d %H:%M:%S"))

    # **Aynı statüye tekrar tekrar giriş yapmamak için kontrol**
    if last_entry:
        last_new_status = last_entry["new_status"]

        if last_new_status == "down" and new_status == "down":
            print(f"🔵 INFO: {hostname} ({deviceid}) zaten DOWN, tekrar eklenmedi.")
            return

        if last_new_status == "up" and new_status == "up":
            print(f"🔵 INFO: {hostname} ({deviceid}) zaten UP, tekrar eklenmedi.")
            return

    # ✅ **Yeni değişiklik loglanacak!**
    new_entry = {
        "log_id": str(uuid.uuid4()),  # ✨ Her kayda benzersiz bir ID ekledik
        "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "deviceid": deviceid,
        "hostname": hostname,
        "serial": serial,
        "old_status": old_status,
        "new_status": new_status,
        "mail_sent": 0  # ✨ Yeni kayıt için 'mail_sent' varsayılan olarak 0!
    }
    status_logs.append(new_entry)

    # **JSON dosyasına yaz**
    try:
        with open(STATUS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_logs, f, indent=2)
        print(f"🟢 LOG: {hostname} ({deviceid}) için {old_status} → {new_status} kaydedildi. (mail_sent=0)")
    except Exception as e:
        print(f"🔴 HATA: JSON güncellenirken hata oluştu: {e}")

def update_status_change(device, previous_data):
    """Cihazın durum değişikliklerini kontrol eder ve sadece belirlenen 3 alanı günceller."""
    deviceid = str(device["deviceid"])
    current_status = device["ping_state"].lower() if isinstance(device["ping_state"], str) else "unknown"

    # Geçersiz veri varsa atla
    if current_status not in ["up", "down"]:
        print(f"⚠️ INFO: {device['hostname']} ({deviceid}) için geçersiz durum atlandı: {current_status}")
        return None

    now = datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%d-%m-%Y %H:%M:%S')

    # Önceki durumu belirle
    previous_status = previous_data.get(deviceid, {}).get("ping_state", current_status)
    last_status_check = previous_data.get(deviceid, {}).get("last_status_check", now)
    last_status_change = previous_data.get(deviceid, {}).get("last_status_change", now)

    # **Durum değişikliği var mı?**
    status_changed = previous_status != current_status

    if status_changed:
        print(f"Status Change Detected: {device['hostname']} (ID: {deviceid}) from {previous_status} to {current_status}.")
        serial = device.get("serial", "Unknown")
        log_status_change(deviceid, device["hostname"], previous_status, current_status, device["serial"])

        last_status_change = now  # Durum değiştiyse güncelle

    # **DOWN → UP geçişinde previous_ping_state 'down' olarak işaretlenecek**
    previous_ping_state = "down" if previous_status == "down" and current_status == "up" else previous_status

    return {
        "previous_ping_state": previous_ping_state,
        "last_status_check": now,
        "last_status_change": last_status_change
    }



def archive_status_logs():
    """Cihaz durum değişikliklerini haftalık olarak arşivler."""

    # Eğer arşiv klasörü yoksa oluştur
    os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

    if not os.path.exists(STATUS_LOG_FILE):
        log_message("🔴 LOG: Status log dosyası bulunamadı, arşivleme yapılmadı.")
        return

    # Mevcut değişiklikleri oku
    try:
        with open(STATUS_LOG_FILE, 'r') as f:
            status_changes = json.load(f)
            if not isinstance(status_changes, list):
                status_changes = []
    except json.JSONDecodeError:
        status_changes = []

    if not status_changes:
        log_message("🔴 LOG: Status log boş, arşivleme yapılmadı.")
        return

    # **Tarih damgalı arşiv dosyasının adını oluştur**
    timestamp = datetime.now(pytz.timezone("Europe/Istanbul")).strftime('%Y-%m-%d')
    archive_file = os.path.join(ARCHIVE_FOLDER, f"device_status_archive_{timestamp}.json")

    # **Arşiv dosyasına yaz**
    try:
        with open(archive_file, 'w', encoding='utf-8') as f:
            json.dump(status_changes, f, indent=2)
        log_message(f"🟢 LOG: Cihaz durum değişiklikleri arşivlendi → {archive_file}")
    except Exception as e:
        log_message(f"🔴 HATA: Arşivleme sırasında hata oluştu: {e}")


def fetch_data(url):
    """Fetch data from API - Direct connection without proxy."""
    try:
        log_message(f"🔧 Bağlantı kuruluyor...")

        response = requests.get(
            url,
            auth=(user, password),
            verify=SSL_VERIFY,
            timeout=60,
              # Proxy kullanma - direkt bağlantı
        )

        if response.status_code == 200:
            log_message(f"✅ SUCCESS: Bağlantı başarılı - {url}")
            return response.json()
        else:
            log_message(f"❌ ERROR {response.status_code}: {url}")
            return None

    except requests.exceptions.RequestException as e:
        log_message(f"❌ FAILED: {url} → {e}")
        return None


# NOC-Turkey grubuna özgü debug fonksiyonları

def debug_noc_turkey_devices():
    """NOC-Turkey grubundaki cihazları detaylı analiz eder"""
    print("=" * 80)
    print("🇹🇷 NOC-TURKEY GRUP ANALİZİ")
    print("=" * 80)

    # 1. Grup bilgilerini kontrol et
    group_url = f"{base_url}cdt_group?fields=id,name,description&links=none&limit=1000"
    try:
        response = requests.get(group_url, auth=(user, password), verify=SSL_VERIFY, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'objects' in data['data'] and data['data']['objects']:
                groups = data['data']['objects'][0]['data']
                turkey_groups = [g for g in groups if
                                 'turkey' in g.get('name', '').lower() or 'noc' in g.get('name', '').lower()]
                print(f"📊 Toplam grup sayısı: {len(groups)}")
                print("🇹🇷 Türkiye ile ilgili gruplar:")
                for group in turkey_groups:
                    print(f"   - {group.get('name', 'N/A')} (ID: {group.get('id', 'N/A')})")
        else:
            print(f"❌ Grup bilgileri alınamadı: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Grup sorgusu hatası: {e}")

    # 2. Son 30 gün içinde eklenen cihazları kontrol et
    print(f"\n📅 SON 30 GÜN İÇİNDE EKLENMİŞ CİHAZLAR:")
    recent_device_url = f"{base_url}cdt_device?fields=id,deviceid,hostname,ipaddress,ping_state,sysObjectID,sysName,sysUpTime,dateAdded&groups=NOC-Turkey&links=none&limit=10000"

    try:
        response = requests.get(recent_device_url, auth=(user, password), verify=SSL_VERIFY, timeout=60)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'objects' in data['data'] and data['data']['objects']:
                devices = data['data']['objects'][0]['data']

                # Tarih filtreleme
                from datetime import datetime, timedelta

                thirty_days_ago = datetime.now() - timedelta(days=30)

                recent_devices = []
                for device in devices:
                    date_added = device.get('dateAdded')
                    if date_added:
                        try:
                            # Tarih formatını parse et (Statseeker formatı genelde UNIX timestamp)
                            if isinstance(date_added, (int, float)):
                                device_date = datetime.fromtimestamp(date_added)
                            elif isinstance(date_added, str):
                                device_date = datetime.strptime(date_added, '%Y-%m-%d %H:%M:%S')
                            else:
                                continue

                            if device_date >= thirty_days_ago:
                                recent_devices.append({
                                    'hostname': device.get('hostname', 'N/A'),
                                    'deviceid': device.get('deviceid', 'N/A'),
                                    'ipaddress': device.get('ipaddress', 'N/A'),
                                    'dateAdded': device_date.strftime('%Y-%m-%d %H:%M:%S')
                                })
                        except Exception as e:
                            print(f"   ⚠️ Tarih parse hatası: {device.get('hostname')} - {e}")

                print(f"📈 Son 30 gün içinde eklenen cihaz sayısı: {len(recent_devices)}")
                for device in recent_devices[-10:]:  # Son 10'unu göster
                    print(f"   🆕 {device['hostname']} ({device['ipaddress']}) - {device['dateAdded']}")
            else:
                print("❌ Cihaz verileri alınamadı - veri yapısı beklenmedik")
        else:
            print(f"❌ Recent devices sorgusu başarısız: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Recent devices hatası: {e}")


def debug_device_inventory_mismatch():
    """Device ve Inventory arasındaki uyumsuzlukları kontrol eder"""
    print(f"\n🔗 DEVICE-INVENTORY UYUMSUZLUK ANALİZİ:")

    data_frames = {}

    for name, url in urls.items():
        try:
            response = requests.get(url, auth=(user, password), verify=SSL_VERIFY, timeout=60)
            if response.status_code == 200:
                data = response.json()
                df = process_data(data)
                data_frames[name] = df
                print(f"✅ {name}: {len(df)} kayıt")
            else:
                print(f"❌ {name}: HTTP {response.status_code}")
                return
        except Exception as e:
            print(f"❌ {name}: {e}")
            return

    if 'device' in data_frames and 'inventory' in data_frames:
        device_df = data_frames['device']
        inventory_df = data_frames['inventory']

        print(f"\n📊 Device DataFrame: {len(device_df)} kayıt")
        print(f"📊 Inventory DataFrame: {len(inventory_df)} kayıt")

        # Device'da olan ama inventory'de olmayan deviceid'ler
        device_ids = set(device_df['deviceid'].astype(str))
        inventory_ids = set(inventory_df['deviceid'].astype(str))

        missing_in_inventory = device_ids - inventory_ids
        missing_in_device = inventory_ids - device_ids

        print(f"❌ Device'da var, Inventory'de yok: {len(missing_in_inventory)} cihaz")
        print(f"❌ Inventory'de var, Device'da yok: {len(missing_in_device)} cihaz")

        if missing_in_inventory:
            print("🔍 Device'da var ama Inventory'de olmayan cihazlar:")
            for device_id in list(missing_in_inventory)[:10]:  # İlk 10'unu göster
                device_info = device_df[device_df['deviceid'].astype(str) == device_id].iloc[0]
                print(f"   - {device_info['hostname']} (ID: {device_id})")

        # Merge işlemi sonucu
        merged = device_df.merge(inventory_df, on='deviceid', how='left')
        print(f"\n🔗 Merge sonrası: {len(merged)} kayıt")

        # Model bilgisi olmayan cihazları say
        no_model = merged['model'].isnull().sum()
        print(f"📄 Model bilgisi olmayan cihaz sayısı: {no_model}")


def debug_model_types():
    """Hangi model türlerinin Unknown olarak işaretlendiğini kontrol eder"""
    print(f"\n🔍 MODEL TİPLERİ ANALİZİ:")

    # Inventory verisini al
    inventory_url = urls['inventory']
    try:
        response = requests.get(inventory_url, auth=(user, password), verify=SSL_VERIFY, timeout=60)
        if response.status_code == 200:
            data = response.json()
            df = process_data(data)

            if not df.empty and 'model' in df.columns:
                # Model dağılımını analiz et
                model_counts = df['model'].value_counts()
                print(f"📊 Toplam unique model sayısı: {len(model_counts)}")
                print(f"📊 Toplam cihaz sayısı: {len(df)}")

                # Device type'ları kontrol et
                df['device_type'] = df['model'].apply(determine_device_type)
                device_type_counts = df['device_type'].value_counts()
                print(f"\n📈 Device Type Dağılımı:")
                for dtype, count in device_type_counts.items():
                    print(f"   {dtype}: {count} cihaz")

                # Unknown olanları detaylandır
                unknown_models = df[df['device_type'] == 'Unknown']['model'].value_counts()
                print(f"\n❓ UNKNOWN olarak işaretlenen modeller:")
                for model, count in unknown_models.head(20).items():
                    print(f"   {model}: {count} cihaz")

        else:
            print(f"❌ Inventory verisi alınamadı: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Model analiz hatası: {e}")


# Bu fonksiyonları update_data() fonksiyonundan ÖNCE ekleyin:

def debug_uuid_assignment(merged_data, uuid_mapping):
    """UUID atama sürecini detaylı debug eder"""
    print("=" * 80)
    print("🆔 UUID ATAMA SÜRECİ DEBUG")
    print("=" * 80)

    current_device_ids = set(str(device["deviceid"]) for _, device in merged_data.iterrows())
    mapped_device_ids = set(uuid_mapping.keys())

    print(f"📊 Mevcut cihaz sayısı (merged_data): {len(current_device_ids)}")
    print(f"📊 UUID mapping'de kayıtlı cihaz: {len(mapped_device_ids)}")

    # Yeni cihazlar (mapping'de olmayan)
    new_devices = current_device_ids - mapped_device_ids
    print(f"🆕 Yeni cihaz sayısı (UUID alacak): {len(new_devices)}")

    if new_devices:
        print("🆕 Yeni cihazlar:")
        for device_id in list(new_devices)[:10]:  # İlk 10'unu göster
            device_info = merged_data[merged_data['deviceid'].astype(str) == device_id].iloc[0]
            print(f"   - {device_info['hostname']} (ID: {device_id})")

    # Mapping'de olan ama artık sistemde olmayan cihazlar
    removed_devices = mapped_device_ids - current_device_ids
    print(f"❌ Sistemden çıkarılan cihaz sayısı: {len(removed_devices)}")

    if removed_devices:
        print("❌ Sistemden çıkarılan cihazlar (UUID'leri geri alınabilir):")
        for device_id in list(removed_devices)[:10]:
            uuid_val = uuid_mapping.get(device_id, 'N/A')
            print(f"   - Device ID: {device_id}, UUID: {uuid_val}")

    print("=" * 80)
    return new_devices, removed_devices


def reclaim_unused_uuids(uuid_mapping, available_uuids, merged_data):
    """Artık kullanılmayan UUID'leri geri al"""
    current_device_ids = set(str(device["deviceid"]) for _, device in merged_data.iterrows())
    mapped_device_ids = set(uuid_mapping.keys())

    # Sistemde artık olmayan cihazların UUID'lerini geri al
    removed_devices = mapped_device_ids - current_device_ids
    reclaimed_count = 0

    if removed_devices:
        print(f"🔄 {len(removed_devices)} cihazın UUID'si geri alınacak...")

        for device_id in removed_devices:
            if device_id in uuid_mapping:
                reclaimed_uuid = uuid_mapping.pop(device_id)
                available_uuids.append(reclaimed_uuid)
                reclaimed_count += 1
                log_message(f"♻️ UUID geri alındı: Device {device_id} → UUID {reclaimed_uuid}")

    print(f"♻️ Toplam {reclaimed_count} UUID geri alındı")
    return reclaimed_count


# Şimdi düzeltilmiş update_data fonksiyonu:
def update_data():
    """Fetch and process data, updating status change information."""
    json_file = 'D:/INTRANET/Netinfo/Data/network_device_inventory.json'

    previous_data = load_previous_data()  # Bu fonksiyon zaten kodunuzda var
    uuid_mapping, available_uuids = load_uuid_mapping()  # Bu da zaten var
    data_frames = {}

    for name, url in urls.items():
        log_message(f"Fetching {name} data...")
        data = fetch_data(url)
        if data:
            df = process_data(data)
            data_frames[name] = df
        else:
            log_message(f"❌ {name} verisi API'den çekilemedi!")

    if 'device' in data_frames and 'inventory' in data_frames:
        merged_data = data_frames['device'].merge(data_frames['inventory'], on='deviceid', how='left')

        merged_data['device_type'] = merged_data['model'].apply(determine_device_type)
        merged_data = merged_data[merged_data['device_type'] != 'Unknown']
        merged_data['ping_state'] = merged_data['ping_state'].astype(str).str.lower()
        merged_data = merged_data[merged_data['hostname'].notnull() & merged_data['deviceid'].notnull()]

        # 🔹 **UUID Debug ve Temizleme**
        new_devices_set, removed_devices_set = debug_uuid_assignment(merged_data, uuid_mapping)

        # Kullanılmayan UUID'leri geri al
        reclaimed_count = reclaim_unused_uuids(uuid_mapping, available_uuids, merged_data)

        if reclaimed_count > 0:
            log_message(f"♻️ {reclaimed_count} UUID geri alındı, available pool: {len(available_uuids)}")

        # Location ve city bilgilerini ekle (zaten kodunuzda var)
        try:
            merged_data['location'] = merged_data.apply(
                lambda row: extract_location(row['hostname'], row['deviceid']),
                axis=1
            )
        except Exception as e:
            log_message(f"❌ HATA: location sütunu oluşturulurken hata: {e}")
            return

        station_mapping = station_info()
        if not station_mapping:
            log_message("❌ ERROR: Station info mapping is empty! Check station-info.json")

        try:
            merged_data['city'] = merged_data['location'].map(lambda x: station_mapping.get(x, 'Unknown'))
        except Exception as e:
            log_message(f"❌ HATA: 'city' sütunu oluşturulürken hata: {e}")
            return

        # 🔹 **UUID Atama - İyileştirilmiş**
        newly_assigned_uuids = set()
        uuid_assignment_count = 0

        print(f"\n🆔 UUID ATAMA BAŞLADI:")
        print(f"Available UUID pool: {len(available_uuids)}")

        for index, row in merged_data.iterrows():
            deviceid = str(row["deviceid"])

            if deviceid not in uuid_mapping:
                if available_uuids:
                    assigned_uuid = available_uuids.pop(0)
                    uuid_mapping[deviceid] = assigned_uuid
                    newly_assigned_uuids.add(assigned_uuid)
                    uuid_assignment_count += 1
                    merged_data.at[index, 'uuid'] = assigned_uuid
                    log_message(f"🆕 UUID atandı: {row['hostname']} ({deviceid}) → {assigned_uuid}")
                else:
                    assigned_uuid = "UUID_NOT_ASSIGNED"
                    merged_data.at[index, 'uuid'] = assigned_uuid
                    log_message(
                        f"⚠️ WARNING: UUID havuzu boş! {row['hostname']} ({deviceid}) için UUID ataması yapılamadı.")
            else:
                # Mevcut UUID'yi kullan
                existing_uuid = uuid_mapping[deviceid]
                merged_data.at[index, 'uuid'] = existing_uuid

        print(f"✅ UUID atama tamamlandı: {uuid_assignment_count} yeni atama")

        merged_data = filter_and_group_devices(merged_data)

        updated_devices = []
        new_devices = []

        for device in merged_data.to_dict(orient='records'):
            status_update = update_status_change(device, previous_data)

            updated_device = {
                "id": device["deviceid"],
                "deviceid": device["deviceid"],
                "hostname": device["hostname"],
                "ipaddress": device["ipaddress"],
                "ping_state": device["ping_state"],
                "serial": device.get("serial", ""),
                "model": device.get("model", ""),
                "device_type": determine_device_type(device.get("model", "")),
                "location": extract_location(device["hostname"], device["deviceid"]),
                "city": station_mapping.get(extract_location(device["hostname"], device["deviceid"]), "Unknown"),
                "uuid": device.get("uuid", "UNKNOWN"),
            }

            if status_update:
                updated_device.update(status_update)

            updated_devices.append(updated_device)

            if str(device["deviceid"]) not in previous_data:
                new_devices.append(device)

        # JSON çıktısı kaydı
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(updated_devices, f, indent=2)

        log_message(f"🟢 LOG: {len(updated_devices)} cihaz verisi güncellendi → {json_file}")

        # Yeni cihaz bildirimi
        if new_devices:
            log_message(f"🆕 {len(new_devices)} yeni cihaz tespit edildi!")
            for new_device in new_devices[:5]:  # İlk 5'ini logla
                log_message(f"   🆕 Yeni cihaz: {new_device['hostname']}")

        # UUID dosyasını güncelle
        remaining_uuids = [uuid for uuid in available_uuids if uuid not in newly_assigned_uuids]
        uuid_data = {"deviceid_uuid_mapping": uuid_mapping, "available_uuids": remaining_uuids}
        uuid_file = 'D:/INTRANET/Netinfo/Data/UUID_Pool.json'
        with open(uuid_file, 'w', encoding='utf-8') as f:
            json.dump(uuid_data, f, indent=2)

        log_message(f"🟢 UUID verisi güncellendi → {uuid_file} (Pool: {len(remaining_uuids)})")
        log_message(f"Update complete. Checked {len(merged_data)} devices.")

    else:
        print("❌ HATA: Device veya Inventory verisi eksik!")
        if 'device' not in data_frames:
            print("   - Device verisi yok!")
        if 'inventory' not in data_frames:
            print("   - Inventory verisi yok!")




def process_data(data):
    """Convert JSON data to Pandas DataFrame."""
    if 'data' in data and 'objects' in data['data']:
        objects = data['data']['objects']
        if objects and isinstance(objects, list) and 'data' in objects[0]:
            return pd.DataFrame(objects[0]['data'])
    log_message("Unexpected data structure")
    return pd.DataFrame()

def determine_device_type(model):
    """Determine the device type based on the model."""
    if not isinstance(model, str):
        return "Unknown"

    SWITCH_MODELS = ["C9300", "WS-C2960X", "WS-C3850", "C9500", "C9300L"]
    ROUTER_MODELS = ["ISR4351", "ISR4451", "8300"]

    if any(sw in model for sw in SWITCH_MODELS):
        return "Switch"
    elif any(rt in model for rt in ROUTER_MODELS):
        return "Router"
    return "Unknown"

def load_previous_data():
    """Önceki cihaz verilerini JSON'dan yükler ve hataları engeller."""
    previous_data_file = 'D:/INTRANET/Netinfo/Data/network_device_inventory.json'
    if os.path.exists(previous_data_file):
        try:
            with open(previous_data_file, 'r', encoding='utf-8') as f:
                return {str(d['deviceid']): d for d in json.load(f)}
        except json.JSONDecodeError:
            log_message("🔴 ERROR: JSON dosyası bozuk, sıfırdan başlatılıyor!")
            return {}
    return {}


def load_uuid_mapping():
    """ UUID Mapping dosyasını güvenli modda yükler. """
    uuid_file = 'D:/INTRANET/Netinfo/Data/UUID_Pool.json'

    if not os.path.exists(uuid_file):
        log_message(f"🔴 ERROR: UUID Mapping dosyası bulunamadı: {uuid_file}")
        return {}, []

    try:
        with open(uuid_file, 'r', encoding='utf-8') as f:
            uuid_data = json.load(f)

        uuid_mapping = uuid_data.get("deviceid_uuid_mapping", {})
        available_uuids = uuid_data.get("available_uuids", [])

        log_message(f"✅ UUID Mapping Yüklendi: {len(uuid_mapping)} cihaz, {len(available_uuids)} boş UUID")
        return uuid_mapping, available_uuids
    except json.JSONDecodeError:
        log_message(f"🔴 ERROR: UUID_Pool.json bozuk, yüklenemedi!")
        return {}, []
    except Exception as e:
        log_message(f"🔴 ERROR: UUID Mapping yüklenirken hata oluştu: {e}")
        return {}, []



def assign_uuid(deviceid, uuid_mapping, available_uuids):
    """Cihaza UUID atar, sadece önceden tanımlanmış boş UUID'lerden seçer. Yeni UUID oluşturmaz."""
    deviceid_str = str(deviceid)

    if deviceid_str in uuid_mapping:
        return uuid_mapping[deviceid_str]  # Eğer zaten atanmış bir UUID varsa, değiştirme.

    if available_uuids:
        new_uuid = available_uuids.pop(0)  # İlk boş UUID'yi al
        uuid_mapping[deviceid_str] = new_uuid
        log_message(f"🆕 Yeni UUID atandı: {deviceid} → {new_uuid}")
        return new_uuid

    log_message(f"⚠️ WARNING: UUID havuzunda boş UUID kalmadı! {deviceid} için UUID ataması yapılamadı.")
    return "UUID_NOT_ASSIGNED"



def save_current_data(devices):
    """Cihaz verilerini günceller ve JSON dosyasına yazar."""
    json_file = 'D:/INTRANET/Netinfo/Data/network_device_inventory.json'

    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(devices, f, indent=2)
        log_message(f"🟢 LOG: Cihaz verileri güncellendi → {json_file}")
    except Exception as e:
        log_message(f"🔴 HATA: JSON dosyası kaydedilirken hata oluştu: {e}")


def extract_location(hostname, deviceid=None):
    """Hostname içinden lokasyon kodunu çıkartır. Geçersiz durumlarda 'Unknown' döner ve log yazar."""
    if not hostname or not isinstance(hostname, str):
        log_message(f"⚠️ WARN: extract_location - geçersiz hostname ({hostname}) tespit edildi. deviceid: {deviceid}")
        return 'Unknown'
    try:
        match = re.search(r'Tr([A-Za-z0-9]+?)(?=csw|sw|ttr)', hostname, re.IGNORECASE)
        return match.group(1) if match else 'Unknown'
    except Exception as e:
        log_message(f"⚠️ ERROR: extract_location - exception. hostname={hostname}, deviceid={deviceid} → {e}")
        return 'Unknown'




def filter_and_group_devices(df):
    """Çift kayıtları engelleyen ve sadece stack bağlı cihazları ayrı tutan fonksiyon."""
    stack_devices = df[df['model'].str.contains("STACK", na=False, case=False)]

    df = df[~df['model'].str.contains("STACK", na=False, case=False)]
    df = df.sort_values(by=['deviceid', 'serial']).drop_duplicates(subset=['deviceid'], keep='first')

    return pd.concat([df, stack_devices])

def station_info():
    """Load station information from station-info.json and map code/alternate_code to town."""
    station_file = 'D:/INTRANET/Netinfo/Data/station-info.json'
    if not os.path.exists(station_file):
        log_message(f"Station info file not found: {station_file}")
        return {}

    try:
        with open(station_file, 'r') as f:
            station_data = json.load(f)

        log_message(f"Station info loaded successfully with {len(station_data)} records.")

        # code ve alternate_code'dan town'a eşleştirme yap
        code_mapping = {}
        for entry in station_data:
            town = entry.get('town', 'Unknown')
            if 'code' in entry:
                code_mapping[entry['code']] = town
            if 'alternate_code' in entry:
                code_mapping[entry['alternate_code']] = town

        return code_mapping
    except Exception as e:
        log_message(f"Error loading station info: {e}")
        return {}

def update_data():
    """Fetch and process data, updating status change information."""
    json_file = 'D:/INTRANET/Netinfo/Data/network_device_inventory.json'

    previous_data = load_previous_data()
    uuid_mapping, available_uuids = load_uuid_mapping()  # UUID listesi yüklendi
    data_frames = {}

    for name, url in urls.items():
        log_message(f"Fetching {name} data...")
        data = fetch_data(url)
        if data:
            df = process_data(data)
            data_frames[name] = df
        else:
            log_message(f"❌ {name} verisi API'den çekilemedi!")

    if 'device' in data_frames and 'inventory' in data_frames:
        merged_data = data_frames['device'].merge(data_frames['inventory'], on='deviceid', how='left')

        merged_data['device_type'] = merged_data['model'].apply(determine_device_type)
        merged_data = merged_data[merged_data['device_type'] != 'Unknown']
        merged_data['ping_state'] = merged_data['ping_state'].astype(str).str.lower()
        merged_data = merged_data[merged_data['hostname'].notnull() & merged_data['deviceid'].notnull()]

        # 🔹 hostname'den 'location' sütunu üretimi (korumalı)
        try:
            merged_data['location'] = merged_data.apply(
                lambda row: extract_location(row['hostname'], row['deviceid']),
                axis=1
            )
        except Exception as e:
            log_message(f"❌ HATA: location sütunu oluşturulurken hata: {e}")
            return

        if 'location' not in merged_data.columns:
            log_message("❌ HATA: 'location' sütunu merged_data içinde bulunamadı!")
            return

        # 🏙️ Şehir eşleştirme işlemi
        station_mapping = station_info()
        if not station_mapping:
            log_message("❌ ERROR: Station info mapping is empty! Check station-info.json")

        try:
            merged_data['city'] = merged_data['location'].map(lambda x: station_mapping.get(x, 'Unknown'))
        except Exception as e:
            log_message(f"❌ HATA: 'city' sütunu oluşturulurken hata: {e}")
            return

        # 🔹 **Eksik UUID’leri Atama**
        newly_assigned_uuids = set()

        for index, row in merged_data.iterrows():
            deviceid = str(row["deviceid"])
            if deviceid not in uuid_mapping:
                if available_uuids:
                    assigned_uuid = available_uuids.pop(0)
                    uuid_mapping[deviceid] = assigned_uuid
                    newly_assigned_uuids.add(assigned_uuid)
                    log_message(f"🆕 UUID atandı: {deviceid} → {assigned_uuid}")
                else:
                    assigned_uuid = "UUID_NOT_ASSIGNED"
                    log_message(f"⚠️ WARNING: UUID havuzunda boş UUID kalmadı! {deviceid} için UUID ataması yapılamadı.")
                merged_data.at[index, 'uuid'] = assigned_uuid
            else:
                merged_data.at[index, 'uuid'] = uuid_mapping[deviceid]

        merged_data = filter_and_group_devices(merged_data)

        updated_devices = []
        new_devices = []

        for device in merged_data.to_dict(orient='records'):
            status_update = update_status_change(device, previous_data)

            updated_device = {
                "id": device["deviceid"],
                "deviceid": device["deviceid"],
                "hostname": device["hostname"],
                "ipaddress": device["ipaddress"],
                "ping_state": device["ping_state"],
                "serial": device.get("serial", ""),
                "model": device.get("model", ""),
                "device_type": determine_device_type(device.get("model", "")),
                "location": extract_location(device["hostname"], device["deviceid"]),
                "city": station_mapping.get(extract_location(device["hostname"], device["deviceid"]), "Unknown"),
                "uuid": device.get("uuid", "UNKNOWN"),
            }

            if status_update:
                updated_device.update(status_update)

            updated_devices.append(updated_device)

            if device["uuid"] == "UUID_NOT_ASSIGNED":
                log_message(f"⚠️ WARNING: {device['hostname']} için UUID bulunamadı!")

            if device["deviceid"] not in previous_data:
                new_devices.append(device)

        # ✅ JSON çıktısı kaydı
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(updated_devices, f, indent=2)

        log_message(f"🟢 LOG: {len(updated_devices)} cihaz verisi güncellendi → {json_file}")

        # ✅ UUID dosyasını güncelle
        remaining_uuids = [uuid for uuid in available_uuids if uuid not in newly_assigned_uuids]
        uuid_data = {"deviceid_uuid_mapping": uuid_mapping, "available_uuids": remaining_uuids}
        uuid_file = 'D:/INTRANET/Netinfo/Data/UUID_Pool.json'
        with open(uuid_file, 'w', encoding='utf-8') as f:
            json.dump(uuid_data, f, indent=2)

        log_message(f"🟢 UUID verisi güncellendi → {uuid_file}")

        log_message(f"Update complete. Checked {len(merged_data)} devices.")




if __name__ == "__main__":
    update_data()
