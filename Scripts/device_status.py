import subprocess
import json
import concurrent.futures

# IP adresleri
ip_addresses = [
    "10.200.33.43",
    "10.206.132.75",
    "10.206.132.74",
    "10.206.132.72",
    "10.206.132.76",
    "10.200.33.3",
    "10.206.155.2"
]


def ping(ip):
    """Belirtilen IP adresine ping atar ve sonucu döner."""
    try:
        # Windows için 'ping' komutu
        result = subprocess.run(['ping', '-n', '4', ip], capture_output=True, text=True, timeout=10)

        if "TTL=" in result.stdout:
            return {"ip": ip, "status": "Aktif", "latency": result.stdout.split("Average =")[1].split("ms")[0].strip()}
        else:
            return {"ip": ip, "status": "Pasif", "latency": "N/A"}
    except subprocess.TimeoutExpired:
        return {"ip": ip, "status": "Zaman Aşımı", "latency": "N/A"}
    except Exception as e:
        return {"ip": ip, "status": "Hata", "latency": str(e)}


def ping_all(ip_list):
    """Tüm IP adreslerine eşzamanlı olarak ping atar."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(ping, ip_list))
    return results


# Ping işlemlerini gerçekleştir
results = ping_all(ip_addresses)

# Sonuçları JSON dosyasına kaydet
output_file = "ping_results.json"
with open(output_file, "w") as f:
    json.dump(results, f, indent=4)

print(f"Ping sonuçları {output_file} dosyasına kaydedildi.")
