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
    now = datetime.datetime.now().strftime('%d %B %Y - %H:%M')
    total = len(newly_offline) + len(newly_online)

    # --- Offline device cards ---
    offline_cards = ""
    for device in newly_offline:
        offline_cards += f"""
            <tr><td style="padding: 0 0 10px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" style="background: #fff; border-radius: 10px; border-left: 4px solid #ef4444; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="padding: 16px 20px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size: 16px; font-weight: 700; color: #1e293b; padding-bottom: 6px;">{device['hostname']}</td>
                                    <td align="right" style="padding-bottom: 6px;">
                                        <span style="display: inline-block; background: #fef2f2; color: #dc2626; font-size: 11px; font-weight: 700; padding: 4px 14px; border-radius: 20px; border: 1px solid #fecaca; letter-spacing: 0.5px;">DOWN</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b;">
                                        <span style="color: #94a3b8; margin-right: 4px;">Seri:</span> {device['serial']}
                                    </td>
                                    <td align="right" style="font-size: 12px; color: #94a3b8;">{device['timestamp']}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td></tr>"""

    # --- Online device cards ---
    online_cards = ""
    for device in newly_online:
        online_cards += f"""
            <tr><td style="padding: 0 0 10px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" style="background: #fff; border-radius: 10px; border-left: 4px solid #22c55e; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="padding: 16px 20px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size: 16px; font-weight: 700; color: #1e293b; padding-bottom: 6px;">{device['hostname']}</td>
                                    <td align="right" style="padding-bottom: 6px;">
                                        <span style="display: inline-block; background: #f0fdf4; color: #16a34a; font-size: 11px; font-weight: 700; padding: 4px 14px; border-radius: 20px; border: 1px solid #bbf7d0; letter-spacing: 0.5px;">UP</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="font-size: 13px; color: #64748b;">
                                        <span style="color: #94a3b8; margin-right: 4px;">Seri:</span> {device['serial']}
                                    </td>
                                    <td align="right" style="font-size: 12px; color: #94a3b8;">{device['timestamp']}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </td></tr>"""

    # --- Offline section ---
    offline_section = ""
    if offline_cards:
        offline_section = f"""
            <!-- Offline Section -->
            <tr><td style="padding: 0 32px 28px 32px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr><td style="padding-bottom: 14px;">
                        <table cellpadding="0" cellspacing="0"><tr>
                            <td style="background: #fef2f2; width: 36px; height: 36px; border-radius: 8px; text-align: center; vertical-align: middle; font-size: 18px;">&#9888;</td>
                            <td style="padding-left: 12px; font-size: 17px; font-weight: 700; color: #dc2626;">Erisilemeyen Cihazlar
                                <span style="display: inline-block; background: #fef2f2; color: #dc2626; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 12px; margin-left: 8px; vertical-align: middle;">{len(newly_offline)}</span>
                            </td>
                        </tr></table>
                    </td></tr>
                    {offline_cards}
                </table>
            </td></tr>"""

    # --- Online section ---
    online_section = ""
    if online_cards:
        online_section = f"""
            <!-- Online Section -->
            <tr><td style="padding: 0 32px 28px 32px;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr><td style="padding-bottom: 14px;">
                        <table cellpadding="0" cellspacing="0"><tr>
                            <td style="background: #f0fdf4; width: 36px; height: 36px; border-radius: 8px; text-align: center; vertical-align: middle; font-size: 18px;">&#10004;</td>
                            <td style="padding-left: 12px; font-size: 17px; font-weight: 700; color: #16a34a;">Duzelen Cihazlar
                                <span style="display: inline-block; background: #f0fdf4; color: #16a34a; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 12px; margin-left: 8px; vertical-align: middle;">{len(newly_online)}</span>
                            </td>
                        </tr></table>
                    </td></tr>
                    {online_cards}
                </table>
            </td></tr>"""

    # --- Summary counters ---
    summary_html = f"""
            <tr><td style="padding: 0 32px 24px 32px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-radius: 12px; overflow: hidden;">
                    <tr>
                        <td width="33%" align="center" style="background: #f8fafc; padding: 18px 12px; border-right: 1px solid #e2e8f0;">
                            <div style="font-size: 28px; font-weight: 800; color: #4D148C;">{total}</div>
                            <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">Toplam Degisiklik</div>
                        </td>
                        <td width="33%" align="center" style="background: #fef2f2; padding: 18px 12px; border-right: 1px solid #e2e8f0;">
                            <div style="font-size: 28px; font-weight: 800; color: #dc2626;">{len(newly_offline)}</div>
                            <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">Kapanan</div>
                        </td>
                        <td width="33%" align="center" style="background: #f0fdf4; padding: 18px 12px;">
                            <div style="font-size: 28px; font-weight: 800; color: #16a34a;">{len(newly_online)}</div>
                            <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">Acilan</div>
                        </td>
                    </tr>
                </table>
            </td></tr>"""

    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cihaz Durum Bildirimi</title>
</head>
<body style="margin: 0; padding: 0; background: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; -webkit-font-smoothing: antialiased;">

    <!-- Outer wrapper -->
    <table width="100%" cellpadding="0" cellspacing="0" style="background: #f1f5f9; padding: 32px 16px;">
        <tr><td align="center">

            <!-- Main card -->
            <table width="640" cellpadding="0" cellspacing="0" style="background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.1);">

                <!-- Header with FedEx gradient -->
                <tr><td style="background: linear-gradient(135deg, #4D148C 0%, #FF6600 100%); padding: 0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <!-- Top accent line -->
                        <tr><td style="height: 4px; background: linear-gradient(90deg, #FF6600, #FFB347, #FF6600);"></td></tr>

                        <!-- Logo + Title -->
                        <tr><td align="center" style="padding: 28px 32px 12px 32px;">
                            <table cellpadding="0" cellspacing="0"><tr>
                                <td style="background: rgba(255,255,255,0.15); width: 52px; height: 52px; border-radius: 14px; text-align: center; vertical-align: middle;">
                                    <img src="{NETINFO_LOGO_URL}" alt="Netinfo" width="32" style="filter: brightness(0) invert(1); opacity: 0.95;">
                                </td>
                                <td style="padding-left: 14px;">
                                    <div style="font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: -0.3px;">Netinfo</div>
                                    <div style="font-size: 12px; color: rgba(255,255,255,0.75); font-weight: 500;">Network Monitoring</div>
                                </td>
                            </tr></table>
                        </td></tr>

                        <!-- Subtitle -->
                        <tr><td align="center" style="padding: 10px 32px 24px 32px;">
                            <div style="font-size: 18px; font-weight: 600; color: #ffffff; margin-bottom: 8px;">Cihaz Durum Bildirimi</div>
                            <div style="display: inline-block; background: rgba(255,255,255,0.18); padding: 6px 16px; border-radius: 20px;">
                                <span style="color: rgba(255,255,255,0.9); font-size: 12px; font-weight: 600;">{now}</span>
                            </div>
                        </td></tr>
                    </table>
                </td></tr>

                <!-- Spacer -->
                <tr><td style="height: 28px;"></td></tr>

                <!-- Summary counters -->
                {summary_html}

                <!-- Sections -->
                {offline_section}
                {online_section}

                <!-- Footer -->
                <tr><td style="background: #f8fafc; padding: 24px 32px; border-top: 1px solid #e2e8f0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                                Bu bildirim <strong style="color: #4D148C;">Netinfo Monitoring</strong> tarafindan otomatik olarak gonderilmistir.
                            </td>
                            <td align="right">
                                <span style="display: inline-block; background: linear-gradient(135deg, #4D148C, #FF6600); color: #fff; padding: 6px 16px; border-radius: 16px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;">Netinfo</span>
                            </td>
                        </tr>
                    </table>
                </td></tr>

            </table>
            <!-- /Main card -->

        </td></tr>
    </table>

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
