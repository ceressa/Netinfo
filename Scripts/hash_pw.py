import hashlib

password = "Ozzy3862500-"
hash_object = hashlib.sha256(password.encode())
hex_dig = hash_object.hexdigest()
print(f"SHA256 hash: {hex_dig}")
