import os
import random
import string
import json

# 📌 Dosya yolları
data_folder = r"D:\INTRANET\Netinfo\Data"
uuid_pool_json = os.path.join(data_folder, "UUID_Pool.json")

# 📌 Rastgele UUID oluşturma fonksiyonu
def generate_random_uuid():
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{random_part}-fdx-{random.randint(1000, 9999)}"

# 📌 UUID_Pool.json'u yükle veya oluştur
if os.path.exists(uuid_pool_json):
    with open(uuid_pool_json, 'r', encoding='utf-8') as json_file:
        uuid_data = json.load(json_file)
        existing_uuid_mapping = uuid_data.get("deviceid_uuid_mapping", {})
        available_uuids = set(uuid_data.get("available_uuids", []))  # Set olarak al ki tekrarlar olmasın
else:
    print(f"{uuid_pool_json} bulunamadı, yeni bir UUID havuzu oluşturuluyor...")
    existing_uuid_mapping = {}
    available_uuids = set()

# 📌 Eksik UUID'leri tamamla (Mevcut sayıyı kontrol et ve eksikleri üret)
required_count = 1000  # Boşta olması gereken UUID sayısı
missing_count = required_count - len(available_uuids)

if missing_count > 0:
    print(f"📌 {missing_count} adet yeni UUID oluşturuluyor...")

    while len(available_uuids) < required_count:
        available_uuids.add(generate_random_uuid())  # Eksik olanları tamamla

# 📌 JSON dosyasını güncelle
uuid_json_output = {
    "deviceid_uuid_mapping": existing_uuid_mapping,
    "available_uuids": list(available_uuids)  # Set → Liste dönüşümü
}

with open(uuid_pool_json, 'w', encoding='utf-8') as json_file:
    json.dump(uuid_json_output, json_file, indent=4, ensure_ascii=False)

print(f"✅ UUID havuzu tamamlandı. UUID_Pool.json dosyası oluşturuldu: {uuid_pool_json}")
print(f"✅ Toplam kullanılmayan UUID sayısı: {len(available_uuids)}")
