import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

master_password = os.environ.get("MASTER_PASSWORD")
hashed_master_password = hashlib.sha256(master_password.encode()).hexdigest()
print(hashed_master_password)
