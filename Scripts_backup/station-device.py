import pandas as pd
import json

# Dosya yolları
network_inventory_file = "D:/INTRANET/Netinfo/Data/network_device_inventory.json"
station_info_file = "D:/INTRANET/Netinfo/Data/station-info.xlsx"
output_excel_file = "D:/INTRANET/Netinfo/Data/Station_Device_Report.xlsx"
output_json_file = "D:/INTRANET/Netinfo/Data/Station_Device_Report.json"

# JSON verisini yükleme
with open(network_inventory_file, "r", encoding="utf-8") as json_file:
    network_data = json.load(json_file)

# JSON verisini DataFrame'e çevirme
device_records = []
for device in network_data:
    hostname = device.get("hostname", "Unknown")
    deviceid = device.get("deviceid", "Unknown")
    for port in device.get("ports", []):
        device_records.append({
            "hostname": hostname,
            "deviceid": deviceid,
            "interface_name": port.get("interface_name", ""),
            "description": port.get("description", ""),
            "link_status": port.get("link_status", "N/A"),
            "neighbor_hostname": port.get("neighbor_hostname", "N/A"),
            "neighbor_port": port.get("neighbor_port", "N/A")
        })

# JSON'dan çekilen veriyi DataFrame'e dönüştürme
network_df = pd.DataFrame(device_records)

# Station Info verilerini yükleme
station_info_df = pd.read_excel(station_info_file)

# Hostname'den CODE çıkarma fonksiyonu
def extract_code_from_hostname(hostname):
    if "Tr" in hostname:
        start_idx = hostname.index("Tr") + 2
        remaining_part = hostname[start_idx:]
        stop_keywords = ["csw", "sw", "tt"]  # Durdurma anahtar kelimeleri

        for keyword in stop_keywords:
            if keyword in remaining_part:
                keyword_idx = remaining_part.index(keyword)
                return remaining_part[:keyword_idx].strip()  # Anahtar kelime öncesini al ve boşlukları temizle
        return remaining_part.strip()  # Eğer anahtar kelime yoksa geri kalanı al
    return None

# CODE sütununu ekleyelim
network_df["CODE"] = network_df["hostname"].apply(extract_code_from_hostname)

# CODE üzerinden birleştirme işlemi
merged_df = pd.merge(network_df, station_info_df, on="CODE", how="left", suffixes=("", "_from_station_info"))

# Eğer CODE eşleşmesi bulunamazsa Alternate Code ile eşleştir
unmatched_df = merged_df[merged_df["Town"].isna()].copy()
alternate_code_df = station_info_df.rename(columns={"Alternate Code": "CODE"})
alternate_code_df = alternate_code_df.loc[:, ~alternate_code_df.columns.duplicated()]  # Tekrarlanan sütunları kaldır

# Alternate Code eşleşmesini yap
alternate_matched_df = pd.merge(unmatched_df, alternate_code_df, on="CODE", how="left", suffixes=("", "_from_alt_code"))

# Eşleşen sonuçları birleştir
final_df = pd.concat([merged_df[~merged_df["Town"].isna()], alternate_matched_df], ignore_index=True)

# Lokasyon bazında cihaz sayısını hesaplama
location_summary = final_df.groupby(
    ["CODE", "Town", "Address", "PostCode", "LATITUDE", "LONGTITUDE", "Maps URL", "Local Contact Name",
     "Local Contact Email", "Local Contact Phone"]
).size().reset_index(name="Device Count")

# Çıktıyı Excel'e kaydetme
with pd.ExcelWriter(output_excel_file) as writer:
    final_df.to_excel(writer, sheet_name="Detailed_Device_Info", index=False)
    location_summary.to_excel(writer, sheet_name="Location_Summary", index=False)

# JSON formatında çıktı oluşturma
output_data = {
    "Detailed_Device_Info": final_df.to_dict(orient="records"),
    "Location_Summary": location_summary.to_dict(orient="records")
}

with open(output_json_file, "w", encoding="utf-8") as json_file:
    json.dump(output_data, json_file, indent=4, ensure_ascii=False)

print(f"Rapor başarıyla oluşturuldu: \nExcel: {output_excel_file}\nJSON: {output_json_file}")
