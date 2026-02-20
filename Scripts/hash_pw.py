import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

password = os.environ.get("HASH_PASSWORD", "")
hash_object = hashlib.sha256(password.encode())
hex_dig = hash_object.hexdigest()
print(f"SHA256 hash: {hex_dig}")
