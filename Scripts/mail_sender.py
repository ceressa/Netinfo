import json
import os
import datetime
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 📌 Set default output encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# 📌 SMTP Server Settings
PRIMARY_SMTP_SERVER = "10.205.176.110"
BACKUP_SMTP_SERVER = "10.205.235.73"
SMTP_PORT = 25

# 📌 Sender & Recipient Information
FROM_ADDRESS = "Netinfo@fedex.com"
TO_ADDRESS = "ufuk.celikeloglu@fedex.com"

# 📌 File Paths
LOGS_FILE = "D:/INTRANET/Netinfo/logs/Latest_Logs/device_status_changes.json"
EMAIL_LOG_FILE = "D:/INTRANET/Netinfo/logs/Latest_Logs/email_log.txt"

# 📌 Netinfo Logo URL
NETINFO_LOGO_URL = "https://tr.eu.fedex.com/Horizon/images/ANKA_transparent.png"


# 📌 Log Function
def log_email(status, message, force_log=False):
    if not force_log and status == "WARNING":
        return

    log_entry = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {status} - {message}\n"
    with open(EMAIL_LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)
    print(log_entry.strip())


# 📌 Load JSON Data
def load_device_status():
    if not os.path.exists(LOGS_FILE):
        log_email("ERROR", "Device status file not found.")
        return []

    with open(LOGS_FILE, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
            valid_logs = [log for log in data if "mail_sent" in log and log["mail_sent"] == 0]
            return valid_logs
        except json.JSONDecodeError:
            log_email("ERROR", "JSON file is corrupted, could not be loaded.")
            return []


# 📌 Update mail_sent Status
def mark_as_sent(entries):
    if not entries:
        return

    try:
        with open(LOGS_FILE, "r", encoding="utf-8") as file:
            all_logs = json.load(file)
    except json.JSONDecodeError:
        log_email("ERROR", "JSON file is corrupted, could not be loaded.")
        return

    updated_logs = []
    for log in all_logs:
        if "mail_sent" in log and log["mail_sent"] == 0:
            if any(e["log_id"] == log.get("log_id") for e in entries):
                log["mail_sent"] = 1
        updated_logs.append(log)

    try:
        with open(LOGS_FILE, "w", encoding="utf-8") as file:
            json.dump(updated_logs, file, indent=4)
        log_email("INFO", f"{len(entries)} records updated and marked as mail_sent=1.")
    except Exception as e:
        log_email("ERROR", f"Error occurred while updating JSON file: {e}")


def generate_email_content(newly_offline, newly_online):
    now = datetime.datetime.now().strftime('%B %d, %Y • %H:%M')

    # 📌 Offline devices table rows
    offline_rows = "".join(
        f"""<tr style="transition: all 0.3s ease; background: {'#ffffff' if i % 2 == 0 else '#fafafa'};">
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9;">
                <div style="display: flex; align-items: center;">
                    <div style="width: 10px; height: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; margin-right: 14px; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);"></div>
                    <span style="font-weight: 600; color: #1e293b; font-size: 15px;">{device['hostname']}</span>
                </div>
            </td>
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9;">
                <div style="display: inline-flex; align-items: center; background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); padding: 8px 16px; border-radius: 30px; border: 1px solid #fca5a5;">
                    <span style="font-size: 12px; margin-right: 6px;">🔴</span>
                    <span style="color: #dc2626; font-weight: 700; font-size: 13px; letter-spacing: 0.3px;">DOWN</span>
                </div>
            </td>
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9; color: #64748b; font-size: 14px; font-weight: 500;">
                {device['timestamp']}
            </td>
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9; color: #94a3b8; font-size: 13px; font-family: 'Courier New', monospace; font-weight: 600;">
                {device['serial']}
            </td>
        </tr>"""
        for i, device in enumerate(newly_offline)
    )

    # 📌 Online devices table rows
    online_rows = "".join(
        f"""<tr style="transition: all 0.3s ease; background: {'#ffffff' if i % 2 == 0 else '#fafafa'};">
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9;">
                <div style="display: flex; align-items: center;">
                    <div style="width: 10px; height: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; margin-right: 14px; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);"></div>
                    <span style="font-weight: 600; color: #1e293b; font-size: 15px;">{device['hostname']}</span>
                </div>
            </td>
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9;">
                <div style="display: inline-flex; align-items: center; background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); padding: 8px 16px; border-radius: 30px; border: 1px solid #86efac;">
                    <span style="font-size: 12px; margin-right: 6px;">🟢</span>
                    <span style="color: #16a34a; font-weight: 700; font-size: 13px; letter-spacing: 0.3px;">UP</span>
                </div>
            </td>
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9; color: #64748b; font-size: 14px; font-weight: 500;">
                {device['timestamp']}
            </td>
            <td style="padding: 20px 24px; border-bottom: 1px solid #f1f5f9; color: #94a3b8; font-size: 13px; font-family: 'Courier New', monospace; font-weight: 600;">
                {device['serial']}
            </td>
        </tr>"""
        for i, device in enumerate(newly_online)
    )

    # 📌 Modern HTML Template
    # 📌 Modern HTML Template
    html_template = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Device Status Update</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    </head>
    <body style="margin: 0; padding: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">

        <div style="max-width: 720px; margin: 40px auto; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 25px 70px rgba(0, 0, 0, 0.35);">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #4D148C 0%, #2d0a54 100%); padding: 30px 40px 35px 40px; text-align: center; position: relative;">
                <div style="position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, #f093fb 0%, #f5576c 33%, #4facfe 66%, #00f2fe 100%);"></div>

                <!-- Refined Logo -->
                <div style="background: rgba(255, 255, 255, 0.08); width: 70px; height: 70px; border-radius: 50%; margin: 0 auto 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 12px rgba(255, 255, 255, 0.15);">
                    <img src="{NETINFO_LOGO_URL}" alt="Netinfo" style="width: 45px; height: auto; filter: brightness(0) invert(1); opacity: 0.95;">
                </div>

                <h1 style="color: #ffffff; font-size: 26px; font-weight: 700; margin: 8px 0 8px 0; letter-spacing: -0.5px;">Device Status Report</h1>
                <p style="color: rgba(255, 255, 255, 0.8); font-size: 14px; margin: 0; font-weight: 500;">
                    Real-time Network Monitoring Alert
                </p>
                <div style="margin-top: 14px; padding: 8px 18px; background: rgba(255, 255, 255, 0.15); border-radius: 30px; display: inline-block; backdrop-filter: blur(8px);">
                    <span style="color: rgba(255, 255, 255, 0.95); font-size: 13px; font-weight: 600;">📅 {now}</span>
                </div>
            </div>

        <!-- Content -->
        <div style="padding: 50px 40px;">

            {f'''
            <!-- Offline Devices Section -->
            <div style="margin-bottom: 40px;">
                <div style="background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%); padding: 24px 28px; border-radius: 16px; border-left: 6px solid #ef4444; margin-bottom: 24px; box-shadow: 0 4px 15px rgba(239, 68, 68, 0.1);">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center;">
                            <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px; box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);">
                                <span style="font-size: 24px;">⚠️</span>
                            </div>
                            <h2 style="color: #dc2626; font-size: 20px; font-weight: 700; margin: 0;">Unreachable Devices</h2>
                        </div>
                        <div style="background: rgba(239, 68, 68, 0.15); padding: 8px 18px; border-radius: 30px;">
                            <span style="color: #dc2626; font-size: 14px; font-weight: 700;">{len(newly_offline)} Device{"s" if len(newly_offline) != 1 else ""}</span>
                        </div>
                    </div>
                </div>

                <div style="background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); border: 1px solid #f1f5f9;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);">
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Device Name</th>
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Status</th>
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Timestamp</th>
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Serial Number</th>
                            </tr>
                        </thead>
                        <tbody>
                            {offline_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            ''' if offline_rows else ''}

            {f'''
            <!-- Online Devices Section -->
            <div style="margin-bottom: 20px;">
                <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); padding: 24px 28px; border-radius: 16px; border-left: 6px solid #22c55e; margin-bottom: 24px; box-shadow: 0 4px 15px rgba(34, 197, 94, 0.1);">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center;">
                            <div style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px; box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);">
                                <span style="font-size: 24px;">✅</span>
                            </div>
                            <h2 style="color: #16a34a; font-size: 20px; font-weight: 700; margin: 0;">Restored Devices</h2>
                        </div>
                        <div style="background: rgba(34, 197, 94, 0.15); padding: 8px 18px; border-radius: 30px;">
                            <span style="color: #16a34a; font-size: 14px; font-weight: 700;">{len(newly_online)} Device{"s" if len(newly_online) != 1 else ""}</span>
                        </div>
                    </div>
                </div>

                <div style="background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); border: 1px solid #f1f5f9;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);">
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Device Name</th>
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Status</th>
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Timestamp</th>
                                <th style="padding: 18px 24px; text-align: left; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 2px solid #e2e8f0;">Serial Number</th>
                            </tr>
                        </thead>
                        <tbody>
                            {online_rows}
                        </tbody>
                    </table>
                </div>
            </div>
            ''' if online_rows else ''}

        </div>

        <!-- Footer -->
        <div style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); padding: 40px; text-align: center; border-top: 1px solid #e2e8f0;">
            <p style="color: #64748b; font-size: 14px; margin: 0 0 20px 0; line-height: 1.7; font-weight: 500;">
                This automated notification was generated by <strong style="color: #4D148C;">Netinfo Monitoring System</strong>
            </p>
            <div style="margin-top: 20px;">
                <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 10px 28px; border-radius: 30px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);">Powered by Netinfo</span>
            </div>
            <div style="margin-top: 25px; padding-top: 25px; border-top: 1px solid #e2e8f0;">
                <p style="color: #94a3b8; font-size: 12px; margin: 0; font-weight: 500;">
                    © 2025 Netinfo Network Monitoring • All rights reserved
                </p>
            </div>
        </div>

    </div>

</body>
</html>"""

    return html_template


# 📌 Send Email
def send_email(subject, html_content):
    message = MIMEMultipart('alternative')
    message['From'] = FROM_ADDRESS
    message['To'] = TO_ADDRESS
    message['Subject'] = subject
    message.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(PRIMARY_SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.sendmail(FROM_ADDRESS, TO_ADDRESS, message.as_string().encode("utf-8"))
        log_email("SUCCESS", f"Email sent to: {TO_ADDRESS}")
    except Exception as e:
        log_email("ERROR", f"Email could not be sent: {e}")


# 📌 Check device changes and send email
def check_device_changes():
    logs = load_device_status()

    if not logs:
        log_email("WARNING", "Log file is empty or could not be read.")
        return

    newly_offline = [log for log in logs if log["new_status"].lower() == "down"]
    newly_online = [log for log in logs if log["new_status"].lower() == "up"]

    if newly_offline or newly_online:
        print(f"\n{'=' * 60}")
        print(f"📊 DEVICE STATUS REPORT")
        print(f"{'=' * 60}")
        print(f"🔴 Offline devices: {len(newly_offline)}")
        print(f"🟢 Online devices: {len(newly_online)}")
        print(f"{'=' * 60}\n")

        email_content = generate_email_content(newly_offline, newly_online)
        send_email("🔔 Device Status Update - Netinfo Monitoring", email_content)
        mark_as_sent(logs)


if __name__ == "__main__":
    check_device_changes()

# if __name__ == "__main__":
#     # 🔹 TEST MAIL GÖNDERME MODU
#     test_offline = [{
#         "hostname": "TEST-SWITCH-001",
#         "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "serial": "ABC123XYZ",
#         "log_id": "TEST-001",
#         "new_status": "down",
#         "mail_sent": 0
#     }]
#
#     test_online = [{
#         "hostname": "TEST-SWITCH-002",
#         "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "serial": "XYZ789ABC",
#         "log_id": "TEST-002",
#         "new_status": "up",
#         "mail_sent": 0
#     }]
#
#     html_content = generate_email_content(test_offline, test_online)
#     send_email("🔔 Test Mail - Netinfo Monitoring", html_content)
#     print("✅ Test mail gönderildi.")
