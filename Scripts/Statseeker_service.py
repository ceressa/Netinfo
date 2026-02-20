import win32serviceutil
import win32service
import win32event
import servicemanager
import logging
import os
import subprocess

class StatseekerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "Netinfo_ss"
    _svc_display_name_ = "Netinfo_ss"
    _svc_description_ = "This service runs the Statseeker Base Python script every 2 minutes."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.setup_logging()

    def setup_logging(self):
        log_dir = "D:/INTRANET/Netinfo/Logs/"
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(log_dir, "StatseekerService.log"),
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def SvcStop(self):
        self.logger.info("Service stop requested.")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.logger.info("Service is starting...")
        self.running = True
        self.main()

    def main(self):
        while self.running:
            try:
                self.logger.info("Executing scheduled task...")
                self.run_script()
                self.logger.info("Task execution completed. Waiting 2 minutes for the next execution.")
            except Exception as e:
                self.logger.error(f"Error occurred: {e}")
            win32event.WaitForSingleObject(self.hWaitStop, 120000)  # 2 minutes delay

    def run_script(self):
        script_path = "D:/INTRANET/Netinfo/Scripts/Statseeker_base.py"
        if not os.path.exists(script_path):
            self.logger.error(f"Script not found: {script_path}")
            return

        try:
            result = subprocess.run(
                ["C:/Py313/python.exe", script_path],
                capture_output=True,
                text=True
            )

            self.logger.info(f"Subprocess STDOUT: {result.stdout}")
            self.logger.info(f"Subprocess STDERR: {result.stderr}")

            if result.returncode == 0:
                self.logger.info("Script executed successfully.")
            else:
                self.logger.error(f"Script execution failed with return code {result.returncode}")
        except Exception as e:
            self.logger.error(f"Failed to execute script: {e}")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(StatseekerService)
