import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

password = os.environ.get("HASH_PASSWORD", "")
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
print(f"Bcrypt hash: {hashed}")
