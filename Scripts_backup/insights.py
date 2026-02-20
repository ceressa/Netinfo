import os
import json
import datetime

# 📍 Dosya yolları
DATA_DIR = "D:\\INTRANET\\Netinfo\\Data"
LOGS_DIR = "D:\\INTRANET\\Netinfo\\logs\\Latest_Logs"
OUTPUT_PATH = "D:\\INTRANET\\Netinfo\\data\\insight_summary.json"

# 📍 Tarihler
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

today_str = today.strftime("%Y-%m-%d")
yesterday_str = yesterday.strftime("%Y-%m-%d")

rush_hour_file_today = f"network_rush_hour_{today_str}.json"
rush_hour_file_yesterday = f"network_rush_hour_{yesterday_str}.json"

# 📍 JSON dosyası oku
def load_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Dosya okunamadı: {file_path} → {e}")
        return None

main_data = load_json(os.path.join(DATA_DIR, "main_data.json"))
inventory = load_json(os.path.join(DATA_DIR, "network_device_inventory.json"))
device_logs = load_json(os.path.join(LOGS_DIR, "device_status_changes.json"))
rush_hour_today = load_json(os.path.join(DATA_DIR, rush_hour_file_today))
rush_hour_yesterday = load_json(os.path.join(DATA_DIR, rush_hour_file_yesterday))

# 📍 Önceki özet
def load_previous_summary():
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, list) and existing:
                    return existing[-1]
        except Exception:
            return None
    return None

# 📍 Yüzde hesapla
def pct_change(new, old):
    try:
        return round(((new - old) / old) * 100, 1)
    except:
        return 0.0

# 📍 Insight üret
def generate_insight():
    now = datetime.datetime.now()
    previous = load_previous_summary()
    summary = {
        "timestamp": now.isoformat(),
        "total_devices": 0,
        "online_devices": 0,
        "offline_devices": 0,
        "top_usage_devices": [],
        "recent_status_changes": [],
        "rush_hour": {
            "min": {},
            "max": {}
        },
        "insights": []
    }

    insights = []

    # 🔵 Cihaz durumu
    if inventory:
        total = len(inventory)
        online = sum(1 for d in inventory if d.get("ping_state") == "up")
        offline = sum(1 for d in inventory if d.get("ping_state") == "down")
        summary["total_devices"] = total
        summary["online_devices"] = online
        summary["offline_devices"] = offline

        if previous:
            prev_online = previous.get("online_devices", 0)
            delta_online = online - prev_online
            pct = pct_change(online, prev_online)
            if delta_online > 0:
                insights.append(f"Çevrimiçi cihaz sayısı önceki özete göre {delta_online} arttı (%{pct}).")
            elif delta_online < 0:
                insights.append(f"Çevrimiçi cihaz sayısı {abs(delta_online)} azaldı (%{abs(pct)}).")

        offline_list = [d["hostname"] for d in inventory if d.get("ping_state") == "down"]
        if offline_list:
            insights.append(f"Şu anda çevrimdışı cihazlar: {', '.join(offline_list[:5])}.")
        else:
            insights.append("Tüm cihazlar çevrimiçi.")

    # 🟡 Trafik yoğunluğu
    if main_data:
        top_level = {
            k: v for k, v in main_data.items()
            if isinstance(v, dict) and "input_mbps" in v and "output_mbps" in v
        }
        sorted_devices = sorted(top_level.items(), key=lambda item: item[1]["input_mbps"] + item[1]["output_mbps"], reverse=True)
        summary["top_usage_devices"] = [{
            "hostname": host,
            "input_mbps": round(data["input_mbps"], 2),
            "output_mbps": round(data["output_mbps"], 2),
            "total_mbps": round(data["input_mbps"] + data["output_mbps"], 2)
        } for host, data in sorted_devices[:5]]

        if previous and previous.get("top_usage_devices"):
            prev_map = {d["hostname"]: d["total_mbps"] for d in previous["top_usage_devices"]}
            for d in summary["top_usage_devices"]:
                if d["hostname"] in prev_map:
                    delta = d["total_mbps"] - prev_map[d["hostname"]]
                    if abs(delta) > 5:
                        direction = "arttı" if delta > 0 else "azaldı"
                        insights.append(f"{d['hostname']} trafiği {abs(delta)} Mbps {direction}.")

    # 🔴 Son 1 saatlik durum değişiklikleri
    if device_logs:
        one_hour_ago = (now - datetime.timedelta(hours=1)).isoformat()
        recent_logs = [log for log in device_logs if log["timestamp"] >= one_hour_ago and log["timestamp"].startswith(today_str)]
        if recent_logs:
            insights.append(f"Son 1 saatte {len(recent_logs)} cihaz durumu değişti.")
        else:
            insights.append("Son 1 saatte hiçbir cihaz durumu değişmedi.")

        today_logs = [log for log in device_logs if log["timestamp"].startswith(today_str)]
        if today_logs:
            sorted_logs = sorted(today_logs, key=lambda x: x["timestamp"], reverse=True)
            summary["recent_status_changes"] = [{
                "hostname": log["hostname"],
                "serial": log["serial"],
                "timestamp": log["timestamp"],
                "status_change": f"{log['old_status'].upper()} → {log['new_status'].upper()}"
            } for log in sorted_logs[:5]]

    # ⏱ Rush Hour
    if rush_hour_today:
        try:
            min_now = min(rush_hour_today, key=lambda h: h["input_traffic_mbps"] + h["output_traffic_mbps"])
            max_now = max(rush_hour_today, key=lambda h: h["input_traffic_mbps"] + h["output_traffic_mbps"])
            summary["rush_hour"]["min"] = {
                "hour_range": str(min_now["hour_range"]),
                "input": float(min_now["input_traffic_mbps"]),
                "output": float(min_now["output_traffic_mbps"])
            }
            summary["rush_hour"]["max"] = {
                "hour_range": str(max_now["hour_range"]),
                "input": float(max_now["input_traffic_mbps"]),
                "output": float(max_now["output_traffic_mbps"])
            }

            if rush_hour_yesterday:
                max_prev = max(rush_hour_yesterday, key=lambda h: h["input_traffic_mbps"] + h["output_traffic_mbps"])
                total_today = max_now["input_traffic_mbps"] + max_now["output_traffic_mbps"]
                total_yesterday = max_prev["input_traffic_mbps"] + max_prev["output_traffic_mbps"]
                delta = round(total_today - total_yesterday, 2)
                pct = pct_change(total_today, total_yesterday)
                if abs(delta) > 10:
                    direction = "arttı" if delta > 0 else "azaldı"
                    insights.append(f"En yoğun trafik saati dünkü değere göre {abs(delta)} Mbps (%{abs(pct)}) {direction}.")
        except Exception as e:
            print(f"⚠️ Rush hour verisi işlenirken hata: {e}")

    summary["insights"] = [str(i) for i in insights]
    return summary

# 📍 JSON çıktısını kaydet
insight = generate_insight()
try:
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, list):
            existing.append(insight)
        else:
            existing = [existing, insight]
    else:
        existing = [insight]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=4)
    print(f"✅ Türkçe zengin özet başarıyla eklendi → {OUTPUT_PATH}")
except Exception as e:
    print(f"❌ Özet kaydedilirken hata oluştu: {e}")
