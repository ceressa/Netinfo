import hashlib

master_password = "Ceres386250"
hashed_master_password = hashlib.sha256(master_password.encode()).hexdigest()
print(hashed_master_password)
