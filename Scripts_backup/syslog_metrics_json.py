# syslog_metrics_json.py - JSON tabanlı hata sayı takip sistemi

import json
import os
from datetime import datetime, timedelta
import pytz
from collections import defaultdict, Counter
import re

# Dosya yolları
DATA_DIR = "D:/INTRANET/Netinfo/Data"
SYSLOG_RAW_FILE = os.path.join(DATA_DIR, "syslog_data.json")
SYSLOG_METRICS_FILE = os.path.join(DATA_DIR, "syslog_metrics.json")
SYSLOG_HOURLY_FILE = os.path.join(DATA_DIR, "syslog_hourly_stats.json")
SYSLOG_DAILY_FILE = os.path.join(DATA_DIR, "syslog_daily_stats.json")

# Hata kategorileri
ERROR_CATEGORIES = {
    "Critical_Device_Issues": {
        "patterns": ["%SYS-5-RESTART", "%SYS-5-SHUTDOWN", "%SYS-1-", "%SYS-2-"],
        "severity": 1,
        "description": "Cihaz restart/shutdown"
    },
    "Network_Link_Issues": {
        "patterns": ["%LINK-3-UPDOWN", "%LINEPROTO-5-UPDOWN.*down"],
        "severity": 2,
        "description": "Network bağlantı sorunları"
    },
    "MAC_Flapping": {
        "patterns": ["%SW_MATM-4-MACFLAP_NOTIF"],
        "severity": 2,
        "description": "MAC adresi titremesi"
    },
    "Power_Issues": {
        "patterns": ["%ILPOWER-5-", "%ILPOWER-3-", "%ILPOWER-7-DETECT"],
        "severity": 3,
        "description": "Güç/PoE sorunları"
    },
    "Security_Violations": {
        "patterns": ["%PORT_SECURITY-2-", "%SEC_LOGIN-4-"],
        "severity": 2,
        "description": "Güvenlik ihlalleri"
    },
    "STP_Changes": {
        "patterns": ["%SPANTREE-2-", "%SPANTREE-6-PORT_STATE"],
        "severity": 3,
        "description": "Spanning Tree değişiklikleri"
    },
    "Other_Warnings": {
        "patterns": [".*"],
        "severity": 4,
        "description": "Diğer uyarılar"
    }
}


def load_json_file(file_path, default_data=None):
    """JSON dosyasını güvenli şekilde yükle"""
    if default_data is None:
        default_data = {}

    if not os.path.exists(file_path):
        return default_data

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if data else default_data
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ {file_path} dosyası bozuk: {e}")
        return default_data


def save_json_file(file_path, data):
    """JSON dosyasını kaydet"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ {file_path} kaydedilemedi: {e}")
        return False


def categorize_error(log_text):
    """Log metnini kategoriye ayır"""
    for category, info in ERROR_CATEGORIES.items():
        for pattern in info["patterns"]:
            if re.search(pattern, log_text, re.IGNORECASE):
                return category, info["severity"]
    return "Other_Warnings", 4


def process_raw_logs_to_hourly_metrics():
    """Ham logları saatlik metriklere dönüştür"""

    # Ham logları yükle
    raw_logs = load_json_file(SYSLOG_RAW_FILE, [])
    if not raw_logs:
        print("⚠️ Ham log dosyası boş veya bulunamadı")
        return

    print(f"📊 {len(raw_logs)} log işleniyor...")

    # Mevcut metrikleri yükle
    existing_metrics = load_json_file(SYSLOG_METRICS_FILE, {})

    # Saatlik metrikler için grupla
    hourly_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    device_names = {}

    processed_count = 0
    for log in raw_logs:
        deviceid = str(log.get('deviceid', 'unknown'))
        hostname = log.get('entity', 'unknown')
        log_text = log.get('text', '')
        log_time = log.get('time', '')

        # Saat anahtarı oluştur
        try:
            if 'UTC' in log_time:
                dt = datetime.strptime(log_time, "%Y-%m-%d %H:%M:%S UTC")
            else:
                dt = datetime.strptime(log_time[:19], "%Y-%m-%d %H:%M:%S")
            hour_key = dt.strftime("%Y-%m-%d_%H")  # 2025-01-21_14
        except:
            continue

        # Hata kategorisini belirle
        error_category, severity = categorize_error(log_text)

        # Sayaçları artır
        hourly_data[hour_key][deviceid][error_category] += 1
        device_names[deviceid] = hostname
        processed_count += 1

    print(f"✅ {processed_count} log kategorilere ayrıldı")

    # Mevcut metriklerle birleştir
    metrics_structure = existing_metrics.get("hourly_metrics", {})

    for hour_key, devices in hourly_data.items():
        if hour_key not in metrics_structure:
            metrics_structure[hour_key] = {}

        for deviceid, categories in devices.items():
            if deviceid not in metrics_structure[hour_key]:
                metrics_structure[hour_key][deviceid] = {
                    "hostname": device_names.get(deviceid, "unknown"),
                    "categories": {}
                }

            # Kategorileri birleştir
            for category, count in categories.items():
                if category in metrics_structure[hour_key][deviceid]["categories"]:
                    metrics_structure[hour_key][deviceid]["categories"][category] += count
                else:
                    metrics_structure[hour_key][deviceid]["categories"][category] = count

    # Metrik dosyasını güncelle
    final_metrics = {
        "last_updated": datetime.now().isoformat(),
        "total_hours_processed": len(metrics_structure),
        "hourly_metrics": metrics_structure
    }

    success = save_json_file(SYSLOG_METRICS_FILE, final_metrics)
    if success:
        print(f"📈 Metrikler güncellendi: {len(metrics_structure)} saat verisi")

    return final_metrics


def generate_hourly_summary():
    """Saatlik özet raporu oluştur"""

    # Metrikleri yükle
    metrics = load_json_file(SYSLOG_METRICS_FILE, {})
    hourly_metrics = metrics.get("hourly_metrics", {})

    if not hourly_metrics:
        print("⚠️ Metrik verisi bulunamadı")
        return

    # Son saati al
    current_hour = datetime.now().strftime("%Y-%m-%d_%H")
    last_hour = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d_%H")

    # Mevcut saatlik özetleri yükle
    hourly_summaries = load_json_file(SYSLOG_HOURLY_FILE, [])

    # Son saat için özet oluştur
    for hour_key in [current_hour, last_hour]:
        if hour_key not in hourly_metrics:
            continue

        # Bu saatin verilerini topla
        hour_data = hourly_metrics[hour_key]
        total_errors = 0
        category_totals = defaultdict(int)
        severity_totals = defaultdict(int)
        device_error_counts = {}

        for deviceid, device_data in hour_data.items():
            hostname = device_data.get("hostname", "unknown")
            categories = device_data.get("categories", {})

            device_total = 0
            for category, count in categories.items():
                category_totals[category] += count
                severity = ERROR_CATEGORIES.get(category, {}).get("severity", 4)
                severity_totals[f"severity_{severity}"] += count
                total_errors += count
                device_total += count

            if device_total > 0:
                device_error_counts[hostname] = device_total

        # En çok hata veren cihazları bul (top 5)
        top_devices = sorted(device_error_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        summary = {
            "hour": hour_key,
            "timestamp": hour_key.replace("_", " ") + ":00:00",
            "total_errors": total_errors,
            "total_affected_devices": len(device_error_counts),
            "categories": dict(category_totals),
            "severity_breakdown": dict(severity_totals),
            "top_problematic_devices": [
                {"hostname": hostname, "error_count": count}
                for hostname, count in top_devices
            ],
            "generated_at": datetime.now().isoformat()
        }

        # Bu saatin özetinin zaten var olup olmadığını kontrol et
        existing_index = next((i for i, s in enumerate(hourly_summaries) if s.get("hour") == hour_key), None)

        if existing_index is not None:
            hourly_summaries[existing_index] = summary
        else:
            hourly_summaries.append(summary)

    # Son 48 saati tut
    hourly_summaries = sorted(hourly_summaries, key=lambda x: x.get("hour", ""), reverse=True)[:48]

    success = save_json_file(SYSLOG_HOURLY_FILE, hourly_summaries)
    if success and hourly_summaries:
        latest = hourly_summaries[0]
        print(f"⏰ Saatlik özet: {latest['total_errors']} hata, {latest['total_affected_devices']} cihaz")


def generate_daily_summary():
    """Günlük özet raporu oluştur"""

    # Saatlik özetleri yükle
    hourly_summaries = load_json_file(SYSLOG_HOURLY_FILE, [])

    if not hourly_summaries:
        print("⚠️ Saatlik özet verisi bulunamadı")
        return

    # Günlük bazda grupla
    daily_data = defaultdict(lambda: {
        "total_errors": 0,
        "affected_devices": set(),
        "categories": defaultdict(int),
        "severity_breakdown": defaultdict(int),
        "hourly_breakdown": []
    })

    for hour_summary in hourly_summaries:
        hour = hour_summary.get("hour", "")
        if not hour:
            continue

        # Günü çıkart (2025-01-21_14 -> 2025-01-21)
        date = hour.split("_")[0]

        daily_data[date]["total_errors"] += hour_summary.get("total_errors", 0)
        daily_data[date]["hourly_breakdown"].append({
            "hour": hour.split("_")[1],
            "errors": hour_summary.get("total_errors", 0)
        })

        # Kategorileri topla
        for category, count in hour_summary.get("categories", {}).items():
            daily_data[date]["categories"][category] += count

        # Severity topla
        for severity, count in hour_summary.get("severity_breakdown", {}).items():
            daily_data[date]["severity_breakdown"][severity] += count

        # Cihazları topla
        for device in hour_summary.get("top_problematic_devices", []):
            daily_data[date]["affected_devices"].add(device.get("hostname", ""))

    # Günlük özetleri oluştur
    daily_summaries = load_json_file(SYSLOG_DAILY_FILE, [])

    for date, data in daily_data.items():
        # En çok hata kategorisini bul
        top_category = max(data["categories"].items(), key=lambda x: x[1]) if data["categories"] else ("None", 0)

        summary = {
            "date": date,
            "total_errors": data["total_errors"],
            "total_affected_devices": len(data["affected_devices"]),
            "top_error_category": top_category[0],
            "top_error_category_count": top_category[1],
            "categories": dict(data["categories"]),
            "severity_breakdown": dict(data["severity_breakdown"]),
            "hourly_trend": sorted(data["hourly_breakdown"], key=lambda x: x["hour"]),
            "generated_at": datetime.now().isoformat()
        }

        # Günlük özetin zaten var olup olmadığını kontrol et
        existing_index = next((i for i, s in enumerate(daily_summaries) if s.get("date") == date), None)

        if existing_index is not None:
            daily_summaries[existing_index] = summary
        else:
            daily_summaries.append(summary)

    # Son 30 günü tut
    daily_summaries = sorted(daily_summaries, key=lambda x: x.get("date", ""), reverse=True)[:30]

    success = save_json_file(SYSLOG_DAILY_FILE, daily_summaries)
    if success and daily_summaries:
        today = daily_summaries[0]
        print(f"📅 Günlük özet: {today['total_errors']} hata, {today['total_affected_devices']} cihaz")


def get_trend_analysis(days=7):
    """Trend analizi raporu"""

    daily_summaries = load_json_file(SYSLOG_DAILY_FILE, [])

    if len(daily_summaries) < 2:
        return {"trend": "Yeterli veri yok"}

    # Son N günü al
    recent_days = daily_summaries[:days]

    # Trend hesapla
    total_errors_today = recent_days[0].get("total_errors", 0)
    total_errors_yesterday = recent_days[1].get("total_errors", 0) if len(recent_days) > 1 else 0

    if total_errors_yesterday > 0:
        change_pct = ((total_errors_today - total_errors_yesterday) / total_errors_yesterday) * 100
    else:
        change_pct = 0

    # Ortalama hesapla
    avg_errors = sum(day.get("total_errors", 0) for day in recent_days) / len(recent_days)

    trend_direction = "artış" if change_pct > 10 else "azalış" if change_pct < -10 else "stabil"

    analysis = {
        "period": f"Son {len(recent_days)} gün",
        "today_errors": total_errors_today,
        "yesterday_errors": total_errors_yesterday,
        "change_percentage": round(change_pct, 1),
        "trend_direction": trend_direction,
        "daily_average": round(avg_errors, 1),
        "above_average": total_errors_today > avg_errors
    }

    return analysis


def cleanup_old_raw_logs():
    """Ham logları temizle ama metrikleri koru"""

    raw_logs = load_json_file(SYSLOG_RAW_FILE, [])
    if not raw_logs:
        return

    # 48 saatten eski logları temizle
    cutoff_time = datetime.now() - timedelta(hours=48)
    cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")

    original_count = len(raw_logs)
    filtered_logs = []

    for log in raw_logs:
        log_time_str = log.get("time", "")
        try:
            if 'UTC' in log_time_str:
                log_dt = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S UTC")
            else:
                log_dt = datetime.strptime(log_time_str[:19], "%Y-%m-%d %H:%M:%S")

            if log_dt > cutoff_time:
                filtered_logs.append(log)
        except:
            # Hatalı tarih formatında olanları da temizle
            continue

    if len(filtered_logs) < original_count:
        success = save_json_file(SYSLOG_RAW_FILE, filtered_logs)
        if success:
            removed_count = original_count - len(filtered_logs)
            print(f"🧹 {removed_count} eski raw log temizlendi")


if __name__ == "__main__":
    print("🚀 JSON tabanlı Syslog Metrics işlemi başlıyor...")

    # 1. Ham logları saatlik metriklere dönüştür
    print("\n📊 1. Ham loglar işleniyor...")
    process_raw_logs_to_hourly_metrics()

    # 2. Saatlik özet oluştur
    print("\n⏰ 2. Saatlik özet oluşturuluyor...")
    generate_hourly_summary()

    # 3. Günlük özet oluştur
    print("\n📅 3. Günlük özet oluşturuluyor...")
    generate_daily_summary()

    # 4. Trend analizi göster
    print("\n📈 4. Trend analizi...")
    trends = get_trend_analysis(7)
    print(f"   Bugün: {trends.get('today_errors', 0)} hata")
    print(f"   Dün: {trends.get('yesterday_errors', 0)} hata")
    print(f"   Trend: {trends.get('trend_direction', 'bilinmiyor')} (%{trends.get('change_percentage', 0)})")

    # 5. Eski ham logları temizle
    print("\n🧹 5. Eski loglar temizleniyor...")
    cleanup_old_raw_logs()

    print("\n✅ Tüm işlemler tamamlandı!")