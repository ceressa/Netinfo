import win32serviceutil
import win32service
import win32event
import subprocess
import time
import os
import sys  # Loglama için eklendi


# fontTools.unicodedata içerisindeki 'script' modülü bu bağlamda gereksizdir ve
# büyük ihtimalle yanlışlıkla eklenmiştir. Bu yüzden kaldırıldı.
# from fontTools.unicodedata import script

class HorizonPublishService(win32serviceutil.ServiceFramework):
    # Service Framework, stop_event'i ve diğer gerekli değişkenleri tanımlamak için
    # init metodunu çağırmadan önce argümanlarla başlatılır.
    # Service Framework'ten türetilen bir sınıfın __init__ metodunun ilk argümanı 'args' olmalıdır.

    _svc_name_ = "HorizonPublishService"
    _svc_display_name_ = "Horizon Publish Automation Service"
    _svc_description_ = "Runs Horizon publish script automatically."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # Servis durdurulma sinyali için event objesi
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        # Servisin çalışacağı ana dizin
        self.base_path = r"D:\INTRANET\Horizon"
        # Servis döngüsünü kontrol eden bayrak
        self.is_running = True

    def SvcStop(self):
        # Servis durdurulma isteği alındığında çağrılır.
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # Döngüyü durdurmak için bayrağı ayarla
        self.is_running = False
        # Event sinyalini gönder
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        # Servisin ana çalışma döngüsü
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)

        while self.is_running:
            try:
                self.run_publish()
            except Exception as e:
                # Hata durumunda loglama (Event Log'a yazılabilir veya bir dosyaya)
                # Basit bir örnek için konsola yazdırıyoruz, gerçek bir serviste Event Log kullanılmalı.
                print(f"Hata oluştu: {e}", file=sys.stderr)

            # stop_event'i bekle. is_running bayrağı False olursa veya bekleme süresi dolarsa devam eder.
            # 60 saniye bekleme süresi (60 * 1000 milisaniye)
            wait_result = win32event.WaitForSingleObject(self.stop_event, 60 * 1000)

            # Eğer event sinyali gelmişse (servis durdurulmuş demektir), döngüyü kır
            if wait_result == win32event.WAIT_OBJECT_0:
                break

    def run_publish(self):
        # Yayımlama (Publish) işlemini yürüten metod
        print("Yayımlama betiği çalıştırılıyor...")

        # Betiği çalıştırmak için gerekli olan tam komut satırı.
        # subprocess.run/Popen komutunu doğrudan çalıştırmak daha temiz ve güvenlidir.
        # Bu, bir batch/cmd betiği olarak daha iyi çalışır.
        publish_script_commands = r"""
@echo off
cd /d D:\INTRANET\Horizon

echo AppPool durduruluyor...
%windir%\system32\inetsrv\appcmd stop apppool /apppool.name:"HorizonPool"
if errorlevel 1 (
    echo AppPool durdurma başarısız. Devam ediliyor...
)

echo Veriler yedekleniyor...
if exist Data\projects_data.json copy Data\projects_data.json projects_data_backup.json >nul
if exist Data\users.json copy Data\users.json users_backup.json >nul

echo Eski publish klasörü siliniyor...
if exist publish rmdir /s /q publish

echo Proje derleniyor ve yayınlanıyor...
dotnet build -c Release --no-restore
if errorlevel 1 (
    echo Derleme (build) başarısız! İşlem durduruluyor.
    goto :START_APPPOL
)

dotnet publish -c Release --no-build -o publish
if errorlevel 1 (
    echo Yayımlama (publish) başarısız! İşlem durduruluyor.
    goto :START_APPPOL
)

echo API klasörü oluşturuluyor...
mkdir publish\wwwroot\api >nul 2>&1

echo Veriler geri yükleniyor...
if exist projects_data_backup.json copy projects_data_backup.json Data\projects_data.json >nul
if exist projects_data_backup.json del projects_data_backup.json

if exist users_backup.json copy users_backup.json Data\users.json >nul
if exist users_backup.json del users_backup.json

echo Klasör izinleri ayarlanıyor...
icacls Data /grant "IIS_IUSRS":(OI)(CI)F >nul
icacls Data /grant "HorizonPool":(OI)(CI)F >nul

:START_APPPOL
echo AppPool başlatılıyor...
%windir%\system32\inetsrv\appcmd start apppool /apppool.name:"HorizonPool"
if errorlevel 1 (
    echo AppPool başlatma başarısız.
)
echo Yayımlama işlemi tamamlandı.
"""
        # subprocess.Popen yerine, betiği doğrudan çalıştırmak için 'cmd /c' kullanılır.
        # Bu, komutların bir Windows kabuğunda doğru sırada yürütülmesini sağlar.
        # cwd (current working directory) ile betiğin çalışacağı dizin ayarlanır.

        process = subprocess.run(
            ["cmd", "/c", publish_script_commands],
            cwd=self.base_path,
            capture_output=True,  # Çıktıyı yakala (hata ayıklama için faydalı)
            text=True,
            shell=False
            # Güvenlik için shell=False kullanmak en iyisidir, ancak burada doğrudan 'cmd /c' çalıştırıyoruz.
        )

        # İşlem çıktılarını ve hatalarını yazdır (hata ayıklama için)
        print("--- Betik Çıktısı ---")
        print(process.stdout)
        print("--- Hata Çıktısı ---")
        print(process.stderr, file=sys.stderr)
        print(f"Betik çıkış kodu: {process.returncode}")


if __name__ == '__main__':
    # win32serviceutil.HandleCommandLine ile servis komutları (install, start, stop vb.) işlenir.
    # Servis adları, başlıkları ve açıklamaları için sınıf değişkenleri kullanılır.
    win32serviceutil.HandleCommandLine(HorizonPublishService)