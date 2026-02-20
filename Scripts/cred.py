import json
import os
import bcrypt
from cryptography.fernet import Fernet
from datetime import datetime
import subprocess
import getpass
import sys
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_FILE = "D:/INTRANET/Netinfo/Config/credentials.json"
KEY_FILE = "D:/INTRANET/Netinfo/Config/secret.key"
SERVICE_NAME = "NetinfoService"

os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)


def generate_key():
    """Generate and save a new encryption key."""
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as key_file:
        key_file.write(key)
    return key


def load_key():
    """Load the encryption key."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as key_file:
            key = key_file.read()
            if len(key) != 44:
                print("Invalid key detected. Regenerating...")
                return generate_key()
            return key
    else:
        return generate_key()


ENCRYPTION_KEY = load_key()


def encrypt_data(data):
    """Encrypt data using Fernet."""
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data):
    """Decrypt data using Fernet."""
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_data.encode()).decode()


def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def load_master_password_hash():
    """Load the hashed master password."""
    stored_master_password_hash = os.environ.get("MASTER_PASSWORD_HASH", "")
    return stored_master_password_hash


def verify_master_password(max_attempts=3):
    """Verify the entered master password with retries."""
    for attempt in range(max_attempts):
        try:
            password = input("Enter the master password: ").strip()
            stored_hash = load_master_password_hash()

            if stored_hash and bcrypt.checkpw(password.encode(), stored_hash.encode()):
                return True
            else:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    print(f"Invalid master password! {remaining} attempts remaining.")
                else:
                    print("Too many failed attempts. Exiting.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            sys.exit(0)

    return False


def check_service_status():
    """Check if service is running."""
    try:
        result = subprocess.run(["sc", "query", SERVICE_NAME],
                                capture_output=True, text=True, check=True)
        return "RUNNING" in result.stdout
    except subprocess.CalledProcessError:
        return False


def stop_service():
    """Stop the Windows service."""
    if not check_service_status():
        print(f"Service {SERVICE_NAME} is not running.")
        return True

    print(f"Stopping service: {SERVICE_NAME}")
    try:
        result = subprocess.run(["sc", "stop", SERVICE_NAME],
                                capture_output=True, text=True, check=True)
        print("Service stopped successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to stop service: {e}")
        return False


def start_service():
    """Start the Windows service."""
    if check_service_status():
        print(f"Service {SERVICE_NAME} is already running.")
        return True

    print(f"Starting service: {SERVICE_NAME}")
    try:
        result = subprocess.run(["sc", "start", SERVICE_NAME],
                                capture_output=True, text=True, check=True)
        print("Service started successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to start service: {e}")
        return False


def create_credentials():
    """Create or overwrite credentials.json."""
    if not verify_master_password():
        return

    username = input("Enter NetDB username: ").strip()
    if not username:
        print("Username cannot be empty!")
        return

    password = input("Enter NetDB password: ").strip()
    if not password:
        print("Password cannot be empty!")
        return

    credentials = {
        "netdb": {
            "username": username,
            "password": encrypt_data(password),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    }

    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=4)
        print("Credentials saved successfully.")
    except Exception as e:
        print(f"Error saving credentials: {e}")


def view_credentials():
    """View credentials (requires master password)."""
    print("Attempting to verify master password...")

    if not verify_master_password():
        print("Master password verification failed.")
        return

    print("Master password verified successfully.")

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"No credentials found at: {CREDENTIALS_FILE}")
        return

    print("Credentials file found, reading...")

    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            credentials = json.load(f)

        print(f"Credentials loaded: {list(credentials.keys())}")

        username = credentials["netdb"]["username"]
        encrypted_password = credentials["netdb"]["password"]
        last_updated = credentials["netdb"].get("last_updated", "Unknown")

        print("Decrypting password...")
        password = decrypt_data(encrypted_password)

        print(f"\nNetDB Credentials:")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Last Updated: {last_updated}")

    except json.JSONDecodeError as e:
        print(f"Credentials file is corrupted! Error: {e}")
    except KeyError as e:
        print(f"Missing field in credentials: {e}")
        print(f"Available keys: {list(credentials.keys()) if 'credentials' in locals() else 'Could not read file'}")
    except Exception as e:
        print(f"Error reading credentials: {e}")
        import traceback
        traceback.print_exc()


def change_password():
    """Change the stored NetDB password."""
    if not verify_master_password():
        return

    if not os.path.exists(CREDENTIALS_FILE):
        print("No credentials found. Use 'create' option first.")
        return

    new_password = input("Enter the new NetDB password: ").strip()
    if not new_password:
        print("Password cannot be empty!")
        return

    # Service durumunu kontrol et ve gerekirse durdur
    service_was_running = check_service_status()
    if service_was_running:
        if not stop_service():
            print("Could not stop service. Password update cancelled.")
            return

    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            credentials = json.load(f)

        credentials["netdb"]["password"] = encrypt_data(new_password)
        credentials["netdb"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=4)
        print("Password updated successfully.")

    except Exception as e:
        print(f"Error updating password: {e}")
    finally:
        # Service çalışıyorsa tekrar başlat
        if service_was_running:
            start_service()


def show_menu():
    """Display the main menu."""
    print("\n" + "=" * 40)
    print("NetDB Credential Manager")
    print("=" * 40)
    print("1. Create credentials")
    print("2. View credentials")
    print("3. Change password")
    print("4. Service status")
    print("5. Exit")
    print("=" * 40)


def check_service_status_menu():
    """Show service status."""
    status = "RUNNING" if check_service_status() else "STOPPED"
    print(f"Service {SERVICE_NAME} status: {status}")


def main():
    """Main program loop."""
    while True:
        show_menu()
        try:
            choice = input("Select option (1-5): ").strip()

            if choice == "1":
                create_credentials()
            elif choice == "2":
                view_credentials()
            elif choice == "3":
                change_password()
            elif choice == "4":
                check_service_status_menu()
            elif choice == "5":
                print("Goodbye!")
                break
            else:
                print("Invalid option! Please select 1-5.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
