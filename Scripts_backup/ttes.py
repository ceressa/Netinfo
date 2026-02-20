import os
import shutil

# 🔹 Kaynak ve hedef dizinler
source_root = r"D:\INTRANET\Netinfo"
target_root = r"D:\INTRANET\Netinfo_test"

# 🔹 Hariç tutulacak klasörler
excluded_dirs = [
    "publish\\logs", "node_modules", "bin", "obj", "wwwroot\\lib"
]

# 🔹 Ana klasör yapısını belirle
folder_structure = {
    "backend": ["Controllers", "Services", "Scripts", "Models", "Utils"],
    "frontend": ["public", "src"],
    "data": ["data", "archives", "logs"],
    "config": [],
    "logs": [],
    "server": ["routes", "middlewares", "utils"],
    "wwwroot": []
}

# 🔹 1️⃣ Yeni klasör yapısını oluştur
print("📂 Yeni klasör yapısı oluşturuluyor...")
for main_folder, subfolders in folder_structure.items():
    main_path = os.path.join(target_root, main_folder)
    os.makedirs(main_path, exist_ok=True)

    for subfolder in subfolders:
        os.makedirs(os.path.join(main_path, subfolder), exist_ok=True)

# 🔹 2️⃣ Belirtilen klasörleri taşırken içeriği organize et
print("\n📦 Dosyalar uygun klasörlere taşınıyor...")
for root, dirs, files in os.walk(source_root):
    if any(excluded in root for excluded in excluded_dirs):
        continue  # Hariç tutulan dizinleri atla

    relative_path = os.path.relpath(root, source_root)

    for file in files:
        source_file = os.path.join(root, file)

        # 🔹 Dosya kategorisine göre hedef klasörü belirle
        if relative_path.startswith("Controllers"):
            target_path = os.path.join(target_root, "backend", "Controllers")
        elif relative_path.startswith("Services"):
            target_path = os.path.join(target_root, "backend", "Services")
        elif relative_path.startswith("Scripts"):
            target_path = os.path.join(target_root, "backend", "Scripts")
        elif relative_path.startswith("Models"):
            target_path = os.path.join(target_root, "backend", "Models")
        elif relative_path.startswith("Utils"):
            target_path = os.path.join(target_root, "backend", "Utils")
        elif relative_path.startswith("Server"):
            target_path = os.path.join(target_root, "server")
        elif relative_path.startswith("Config"):
            target_path = os.path.join(target_root, "config")
        elif relative_path.startswith("Logs"):
            target_path = os.path.join(target_root, "logs")
        elif relative_path.startswith("Data"):
            target_path = os.path.join(target_root, "data", "data")  # Hepsi "data" altına gidecek
        elif relative_path.startswith("Archives"):
            target_path = os.path.join(target_root, "data", "archives")  # Eski arşivler
        elif relative_path.startswith("frontend"):
            target_path = os.path.join(target_root, "frontend")
        elif relative_path.startswith("wwwroot"):
            target_path = os.path.join(target_root, "wwwroot")  # Statik dosyalar için
        elif relative_path.startswith("publish/wwwroot"):
            target_path = os.path.join(target_root, "publish", "wwwroot")  # Dotnet publish çıktılarını tutacağız
        elif file in ["Program.cs", "appsettings.json", "appsettings.Development.json"]:
            target_path = os.path.join(target_root, "backend")  # Backend'in kök dizinine
        elif file in ["index.html", "site.css", "site.js", "translations.js"]:
            target_path = os.path.join(target_root, "frontend", "src")  # Frontend'e
        else:
            target_path = target_root  # Diğer her şey için varsayılan olarak kök dizin

        os.makedirs(target_path, exist_ok=True)

        destination_file = os.path.join(target_path, file)

        if os.path.exists(destination_file):
            continue  # Zaten varsa tekrar yazma

        try:
            shutil.copy2(source_file, destination_file)
            print(f"📄 {file} taşındı -> {target_path}")
        except Exception as e:
            print(f"⚠️ {file} taşınırken hata oluştu: {e}")

print("\n🎯 **Tüm işlemler tamamlandı!** 🚀")
