from PIL import Image
import os

# 📌 Girdi ve Çıktı Dizinleri
input_logo_path = "D:/INTRANET/Netinfo/publish/wwwroot/Netinfo_logo_text_combined.png"  # Orijinal logo
output_dir = "D:/INTRANET/Netinfo/publish/wwwroot/resized_logos"  # Küçük logoların kaydedileceği klasör

# 📌 Çıktı Boyutları (Küçük, Orta, Büyük)
sizes = {
    "small": (100, 100),
    "medium": (150, 150),
    "large": (200, 200)
}

# 📌 Klasörü oluştur (varsa geç)
os.makedirs(output_dir, exist_ok=True)

# 📌 Logo boyutlarını küçültme
try:
    with Image.open(input_logo_path) as img:
        file_name, file_ext = os.path.splitext(os.path.basename(input_logo_path))  # Dosya adını ve uzantısını al
        for size_name, dimensions in sizes.items():
            resized_img = img.resize(dimensions, Image.Resampling.LANCZOS)  # Pillow 10+ için uygun yöntem
            output_path = os.path.join(output_dir, f"{file_name}_{size_name}{file_ext}")  # Orijinal isim korunuyor
            resized_img.save(output_path)
            print(f"✅ {size_name.capitalize()} logo kaydedildi → {output_path}")

except Exception as e:
    print(f"🔴 HATA: Logo yeniden boyutlandırılamadı! {e}")
