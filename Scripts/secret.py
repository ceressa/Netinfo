import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

master_password = os.environ.get("MASTER_PASSWORD")
hashed_master_password = bcrypt.hashpw(master_password.encode(), bcrypt.gensalt()).decode()
print(hashed_master_password)
