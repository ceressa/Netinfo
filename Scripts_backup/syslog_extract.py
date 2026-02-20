import requests
import json
import os
from datetime import datetime, timedelta
import pytz

# Proxy ayarları
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

# 🔥 OPTIMIZE EDİLDİ - Ana limitler
SYSLOG_LIMIT = 5000  # 100K'dan 5K'ya düşürüldü
MAX_FILE_SIZE_MB = 100  # Maksimum dosya boyutu kontrolü
MAX_LOG_AGE_HOURS = 48  # Maksimum log yaşı

# API bağlantı bilgileri
base_url = "https://statseeker.emea.fedex.com/api/v2.1/"
user = "tr-api"
password = "F3xpres!"

# API'den çekilecek alanlar
fields = {
    "syslog": "deviceid,entity,time,text"
}

# 🔧 DÜZELTİLDİ - Limit parametresi artık SYSLOG_LIMIT kullanıyor
urls = {
    name: f"{base_url}{name}?fields={fields[name]}&groups=NOC-Turkey&links=none&limit={SYSLOG_LIMIT}&ping_state_formats=state_time"
    for name in fields
}

# Log ayarları
log_directory = "D:/INTRANET/Netinfo/Logs/Latest_Logs"
os.makedirs(log_directory, exist_ok=True)

log_start_date = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y%m%d")
log_file_path = os.path.join(log_directory, f"syslog_data_{log_start_date}.log")

# JSON verilerinin saklanacağı dosya
DATA_DIR = "D:/INTRANET/Netinfo/Data"
os.makedirs(DATA_DIR, exist_ok=True)

syslog_json_file = os.path.join(DATA_DIR, "syslog_data.json")


def get_file_size_mb(file_path):
    """Dosya boyutunu MB olarak döndür"""
    if os.path.exists(file_path):
        return os.path.getsize(file_path) / (1024 * 1024)
    return 0


def log_message(message):
    """Log mesajlarını dosyaya yazar."""
    global log_start_date
    current_date = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y%m%d")

    if current_date != log_start_date:
        log_start_date = current_date
        global log_file_path
        log_file_path = os.path.join(log_directory, f"syslog_data_{current_date}.log")

    timestamp = datetime.now(pytz.timezone("Europe/Istanbul")).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {message}\n"

    try:
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
    except Exception as e:
        print(f"🔴 HATA: Log dosyasına yazılırken hata oluştu: {e}")


def fetch_syslog_data():
    """Statseeker API'den syslog mesajlarını çeker ve JSON olarak kaydeder."""
    url = urls["syslog"]
    try:
        log_message(f"📡 API çağrısı yapılıyor... (Limit: {SYSLOG_LIMIT})")
        response = requests.get(url, auth=(user, password), verify=False, timeout=60, proxies=PROXY)

        # HTTP Yanıt Kontrolü
        if response.status_code != 200:
            log_message(f"🔴 HATA: API'den geçersiz yanıt! HTTP {response.status_code}")
            return []

        data = response.json()
        if "data" in data and "objects" in data["data"]:
            syslog_objects = data["data"]["objects"]
            if syslog_objects and isinstance(syslog_objects, list) and "data" in syslog_objects[0]:
                logs = syslog_objects[0]["data"]

                # Zaman damgasını insan okunur hale getir
                for log in logs:
                    log["time"] = datetime.fromtimestamp(log["time"], pytz.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

                log_message(f"🟢 {len(logs)} adet syslog mesajı başarıyla çekildi!")
                return logs

        log_message("⚠️ Uyarı: Beklenen JSON formatında veri bulunamadı!")
        return []
    except requests.exceptions.RequestException as e:
        log_message(f"🔴 Hata: API'den veri çekilirken hata oluştu: {e}")
        return []


def load_existing_syslog_data():
    """Mevcut syslog JSON dosyasını yükler ve en son eklenen log zamanını döndürür."""
    if not os.path.exists(syslog_json_file):
        return [], None  # Eğer dosya yoksa, boş liste dön

    try:
        with open(syslog_json_file, "r", encoding="utf-8") as f:
            existing_logs = json.load(f)
            if existing_logs:
                last_log_time = max(log["time"] for log in existing_logs)
                return existing_logs, last_log_time
            return [], None
    except json.JSONDecodeError:
        log_message("🔴 HATA: JSON dosyası bozuk, yüklenemedi. Yeni dosya oluşturuluyor.")
        return [], None


def cleanup_old_logs(logs):
    """Eski logları temizle - MAX_LOG_AGE_HOURS'dan eski olanları sil"""
    if not logs:
        return logs

    cutoff_time = datetime.now(pytz.utc) - timedelta(hours=MAX_LOG_AGE_HOURS)
    cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S UTC")

    original_count = len(logs)
    filtered_logs = []

    for log in logs:
        log_time_str = log.get("time", "")
        try:
            if log_time_str > cutoff_str:  # String karşılaştırması yeterli (ISO format)
                filtered_logs.append(log)
        except:
            continue  # Hatalı tarih formatlarını atla

    removed_count = original_count - len(filtered_logs)
    if removed_count > 0:
        log_message(f"🧹 {removed_count} eski log temizlendi ({MAX_LOG_AGE_HOURS} saatten eski)")

    return filtered_logs


def save_syslog_data(new_logs):
    """Syslog verilerini kaydet - boyut kontrolü ve temizlik ile"""

    # 🔥 Dosya boyutu kontrolü
    current_size_mb = get_file_size_mb(syslog_json_file)
    log_message(f"📊 Mevcut dosya boyutu: {current_size_mb:.1f}MB")

    if current_size_mb > MAX_FILE_SIZE_MB:
        log_message(f"⚠️ UYARI: Dosya boyutu {MAX_FILE_SIZE_MB}MB'dan büyük. Eski loglar temizleniyor...")

        # Backup al
        if os.path.exists(syslog_json_file):
            backup_file = syslog_json_file.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            try:
                os.rename(syslog_json_file, backup_file)
                log_message(f"📦 Backup oluşturuldu: {backup_file}")
            except:
                pass
        existing_logs = []
        last_log_time = None
    else:
        existing_logs, last_log_time = load_existing_syslog_data()

    log_message(f"📌 Mevcut kayıt sayısı: {len(existing_logs)}")

    # Sadece yeni olanları ekle
    if last_log_time:
        filtered_logs = [log for log in new_logs if log["time"] > last_log_time]
    else:
        filtered_logs = new_logs  # Eğer hiç log yoksa, tüm verileri al

    if filtered_logs:
        # Yeni logları ekle
        all_logs = existing_logs + filtered_logs

        # Eski logları temizle
        all_logs = cleanup_old_logs(all_logs)

        # Duplicate logları kaldır
        seen_logs = set()
        unique_logs = []
        for log in all_logs:
            log_key = f"{log.get('deviceid', '')}_{log.get('time', '')}_{log.get('text', '')[:50]}"
            if log_key not in seen_logs:
                seen_logs.add(log_key)
                unique_logs.append(log)

        try:
            with open(syslog_json_file, "w", encoding="utf-8") as f:
                json.dump(unique_logs, f, indent=2)

            final_size_mb = get_file_size_mb(syslog_json_file)
            log_message(f"🟢 {len(filtered_logs)} yeni syslog mesajı eklendi")
            log_message(f"📁 Toplam log sayısı: {len(unique_logs)}")
            log_message(f"📊 Final dosya boyutu: {final_size_mb:.1f}MB")

        except Exception as e:
            log_message(f"🔴 HATA: Syslog JSON dosyası kaydedilirken hata oluştu: {e}")
    else:
        log_message("✅ Güncellenecek yeni kayıt bulunamadı, dosya aynı kaldı.")


if __name__ == "__main__":
    log_message("🚀 Optimized Syslog Extract başlatılıyor...")
    log_message(f"⚙️ Ayarlar: Limit={SYSLOG_LIMIT}, Max Size={MAX_FILE_SIZE_MB}MB, Max Age={MAX_LOG_AGE_HOURS}h")

    syslog_data = fetch_syslog_data()
    if syslog_data:
        save_syslog_data(syslog_data)
    else:
        log_message("❌ Syslog verisi alınamadı")