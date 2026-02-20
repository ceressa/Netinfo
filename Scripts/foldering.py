import os
import shutil

# Kaynak ve hedef klasörler
source_path = r"D:\INTRANET\Netinfo"
destination_path = r"D:\INTRANET\Netinfo_prod"

# Dosya taşıma kuralları (Kaynak: Dosya, Hedef: Klasör)
file_mappings = {
    # Core
    "Program.cs": "src/Core",
    "Models/ErrorViewModel.cs": "src/Core/Models",
    "Services/AdminAuthService.cs": "src/Core/Services",
    "Services/DeviceDataService.cs": "src/Core/Services",
    "Services/IAdminAuthService.cs": "src/Core/Interfaces",

    # Infrastructure
    "Data/device_config_history.json": "src/Infrastructure/Database",
    "Data/main_router_data.json": "src/Infrastructure/Database",
    "Data/network_device_inventory.json": "src/Infrastructure/Database",
    "Data/UUID_Pool.json": "src/Infrastructure/Database",
    "Data/syslog_data.json": "src/Infrastructure/Logging",

    # Presentation
    "Controllers/AdminController.cs": "src/Presentation/Controllers",
    "Controllers/AdminLogController.cs": "src/Presentation/Controllers",
    "Controllers/DeviceController.cs": "src/Presentation/Controllers",
    "Views/Home/Index.cshtml": "src/Presentation/Views",
    "Views/Shared/_Layout.cshtml": "src/Presentation/Views",
    "wwwroot/deviceinfo.html": "src/Presentation/Views",

    # wwwroot (Statik Dosyalar)
    "styles.css": "wwwroot/css",
    "Netinfo.js": "wwwroot/js",
    "js/translations.js": "wwwroot/js",
    "FedEx_logo.png": "wwwroot/images",
    "wwwroot/favicon.ico": "wwwroot/images",

    # Config
    ".env": "config",
    "appsettings.json": "config",
    "appsettings.Development.json": "config",
    "Config/aes_secret.key": "config",
    "Config/credentials.json": "config",
    "Config/encryption_key.key": "config",
    "Config/master.key": "config",
    "Config/secret.key": "config",

    # Data
    "Data/main_data.json": "data",
    "Data/main_data.xlsx": "data",
    "Data/network_rush_hour_2025-03-03.json": "data/reports",
    "Data/network_rush_hour_2025-03-04.json": "data/reports",
    "Data/Archives/archive_20250217.json": "data/archives",
    "Data/Archives/archive_20250304.json": "data/archives",

    # Scripts
    "Scripts/allinone.py": "scripts",
    "Scripts/device_status.py": "scripts",
    "Scripts/fetch_netdb.py": "scripts",
    "Scripts/fetch_vlan_data.py": "scripts",
    "Scripts/mail_sender.py": "scripts",
    "Scripts/syslog_analysis.py": "scripts",
    "Scripts/uuid_generator.py": "scripts",

    # Tests
    "Test.py": "tests",
    "TEst2.py": "tests",
    "Testt.py": "tests"
}

# Kopyalama işlemi
for file, target_folder in file_mappings.items():
    source_file = os.path.join(source_path, file)
    destination_folder = os.path.join(destination_path, target_folder)
    destination_file = os.path.join(destination_folder, os.path.basename(file))

    # Hedef klasörü oluştur
    os.makedirs(destination_folder, exist_ok=True)

    # Dosya var mı kontrol et, yoksa kopyala
    if not os.path.exists(destination_file):
        shutil.copy2(source_file, destination_file)
        print(f"✅ Kopyalandı: {file} -> {target_folder}")
    else:
        print(f"⚠️ Zaten var: {destination_file}")

print("\n🎉 Tüm dosyalar başarıyla kopyalandı!")
