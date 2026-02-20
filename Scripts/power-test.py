import smtplib
import requests
import urllib3

# Proxy bilgileri (Sözlük olarak tanımlandı)
PROXY = {
    "http": "http://eu-proxy.tntad.fedex.com:9090",
    "https": "http://eu-proxy.tntad.fedex.com:9090"
}

SMTP_SERVER = "10.205.176.110"
SMTP_PORT = 25

# Proxy üzerinden SMTP bağlantısını test etmek için HTTP istek atıyoruz
test_url = f"http://{SMTP_SERVER}:{SMTP_PORT}"
try:
    response = requests.get(test_url, timeout=10)

    if response.status_code == 200:
        print("✅ Proxy üzerinden SMTP sunucusuna erişim başarılı!")
    else:
        print(f"⚠️ Proxy bağlantısı kuruldu ancak SMTP sunucusundan beklenmeyen yanıt: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"❌ Proxy veya SMTP bağlantı hatası: {e}")

# SMTP sunucusuna doğrudan bağlanmayı dene
try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20)
    server.ehlo()
    print("✅ SMTP sunucusuna doğrudan başarıyla bağlanıldı!")
    server.quit()
except Exception as e:
    print(f"❌ SMTP doğrudan bağlantı hatası: {e}")
