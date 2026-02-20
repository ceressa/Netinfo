import os
import win32serviceutil
import win32service
import win32event
import servicemanager
import schedule
import time
import subprocess
import logging
from datetime import datetime
import pytz  # TR saatine göre zamanlama için eklendi

# 📌 Türkiye saat dilimi
TR_TIMEZONE = pytz.timezone("Europe/Istanbul")

# 📌 Log dizini ve dosya ayarları
LOG_DIR = "D:/INTRANET/Netinfo/Logs/Latest_Logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_date = datetime.now(TR_TIMEZONE).strftime("%Y%m%d")
log_file_path = os.path.join(LOG_DIR, f"Scheduled_{log_date}.log")

logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 📌 Log yazma fonksiyonu
def log_message(message):
    """Log mesajlarını yazma fonksiyonu"""
    global log_date, log_file_path
    current_date = datetime.now(TR_TIMEZONE).strftime("%Y%m%d")

    if current_date != log_date:
        log_date = current_date
        log_file_path = os.path.join(LOG_DIR, f"Scheduled_{current_date}.log")
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            encoding="utf-8"
        )

    logging.info(message)

# 📌 Yaklaşan job'ları log'la
def log_scheduled_jobs():
    """Planlanan görevleri log dosyasına yazdır"""
    upcoming_jobs = schedule.get_jobs()
    if not upcoming_jobs:
        log_message("⚠️ Şu an planlanmış hiçbir görev yok.")
        return

    log_message("📌 Yaklaşan Görevler:")
    for job in upcoming_jobs:
        log_message(f"🕒 {job.next_run.strftime('%Y-%m-%d %H:%M:%S')} - {job.job_func.__name__}")

class NetinfoService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NetinfoService"
    _svc_display_name_ = "Netinfo Task Scheduler Service"
    _svc_description_ = "A service to schedule and execute Python scripts for Netinfo."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.router_ports_running = False

    def SvcStop(self):
        """Servisi durdurma işlemi"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        log_message("⚠️ Service Stopped.")

    def SvcDoRun(self):
        """Servisi başlatma işlemi"""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        log_message("✅ Service Started.")
        self.main()

    def run_script(self, script_path):
        """Python script çalıştır ve sonucu logla"""
        script_name = os.path.basename(script_path)
        log_message(f"🔵 JOB BAŞLADI: {script_name}")

        try:
            result = subprocess.run(["python", script_path], capture_output=True, text=True)
            if result.returncode == 0:
                log_message(f"✅ JOB BAŞARIYLA TAMAMLANDI: {script_name}")
            else:
                log_message(f"❌ JOB HATA VERDİ: {script_name}\nHata: {result.stderr.strip()}")
        except Exception as e:
            log_message(f"❌ JOB ÇALIŞTIRILAMADI: {script_name}\nHata: {e}")

    def statseeker_task(self):
        """Statseeker verisini her 2 dakikada bir çalıştır."""
        self.run_script("D:/INTRANET/Netinfo/Scripts/statseeker_base.py")

    def switch_ports_task(self):
        """Switch Ports scripti 07:00 - 20:00 arasında çalıştırılır."""
        now = datetime.now(TR_TIMEZONE)
        if 1 <= now.hour < 23 and not self.router_ports_running:
            self.run_script("D:/INTRANET/Netinfo/Scripts/switch_ports.py")

    def ap_data_task(self):
        """AP data scripti her 15 dakikada bir çalıştırılır."""
        self.run_script("D:/INTRANET/Netinfo/Scripts/ap_data.py")

    def router_ports_task(self):
        """Router Ports scripti çalıştırılır ve öncelikli olarak tamamlanır."""
        self.router_ports_running = True
        self.run_script("D:/INTRANET/Netinfo/Scripts/router_ports.py")
        self.router_ports_running = False

    def archive_task(self):
        """Arşivleme scripti her gece 23:58'de çalıştırılır."""
        self.run_script("D:/INTRANET/Netinfo/Scripts/archive.py")

    def mail_sender_task(self):
        """Mail kontrol scripti dakikada bir çalıştırılır, sadece hata alırsa loglanır."""
        script_path = "D:/INTRANET/Netinfo/Scripts/mail_sender.py"
        script_name = os.path.basename(script_path)

        try:
            result = subprocess.run(["python", script_path], capture_output=True, text=True)
            if result.returncode != 0:
                log_message(f"❌ JOB HATA VERDİ: {script_name}\nHata: {result.stderr.strip()}")
        except Exception as e:
            log_message(f"❌ JOB ÇALIŞTIRILAMADI: {script_name}\nHata: {e}")

    def syslog_task(self):
        """Saat başı syslog verisini çekip analiz eder - OPTIMIZE EDİLDİ"""

        # 1. Önce optimized extract script'ini çalıştır
        self.run_script("D:/INTRANET/Netinfo/Scripts/syslog_extract_optimized.py")

        # 2. Sonra mevcut analysis script'ini çalıştır
        self.run_script("D:/INTRANET/Netinfo/Scripts/syslog_analysis.py")

    def syslog_metrics_task(self):
        """Saatlik metrik toplama ve analiz"""
        self.run_script("D:/INTRANET/Netinfo/Scripts/syslog_metrics_json.py")

    def syslog_cleanup_task(self):
        """Günlük syslog temizlik - YENI"""
        # Her gece eski raw logları temizle ama metrikleri koru
        self.run_script("D:/INTRANET/Netinfo/Scripts/syslog_cleanup.py")

    def insight_task(self):
        """Saat başı içgörüleri üretir ve özet dosyasına ekler."""
        self.run_script("D:/INTRANET/Netinfo/Scripts/insights.py")

    def main(self):
        """Planlanmış görevleri ayarla ve çalıştır."""

        # 🔄 TEMEL GÖREVLER
        schedule.every(2).minutes.do(self.statseeker_task)  # Her 2 dakika - cihaz durumu
        schedule.every(10).minutes.do(self.switch_ports_task)  # Her 10 dakika - switch portları
        schedule.every(15).minutes.do(self.ap_data_task)  # Her 15 dakika - ap data
        schedule.every(1).minutes.do(self.mail_sender_task)  # Her dakika - mail kontrolü

        # 🕐 SAATLIK GÖREVLER
        schedule.every().hour.at(":00").do(self.syslog_task)  # Saat başı - syslog çek
        schedule.every().hour.at(":05").do(self.syslog_metrics_task)  # 5 dakika sonra - metrik analiz
        schedule.every().hour.at(":10").do(self.insight_task)  # 10 dakika sonra - içgörü

        # 📅 GÜNLÜK GÖREVLER
        schedule.every().day.at("00:05").do(self.router_ports_task)  # Gece 00:05 - router portları
        schedule.every().day.at("02:00").do(self.syslog_cleanup_task)  # Gece 02:00 - syslog temizlik
        schedule.every().day.at("23:58").do(self.archive_task)  # Gece 23:58 - arşivleme

        # 📌 Servis başlarken tüm job'ları log'la
        log_scheduled_jobs()

        # 📌 Her 6 saatte bir job listesini yeniden log'la
        schedule.every(6).hours.do(log_scheduled_jobs)

        # 🔄 Ana çevrim
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Her 60 saniyede bir kontrol et
            except Exception as e:
                log_message(f"❌ Unexpected error in main loop: {e}")
                time.sleep(60)  # Hata durumunda da bekle

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(NetinfoService)
