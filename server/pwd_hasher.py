import hashlib
import base64
import os

def pbkdf2_sha256_hash(password: str, iterations: int = 1000000, salt_length: int = 16) -> str:
    # Generate a random salt
    salt = base64.urlsafe_b64encode(os.urandom(salt_length)).rstrip(b'=').decode()

    # Convert password to bytes
    password_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')

    # Derive the key using PBKDF2-HMAC-SHA256
    dk = hashlib.pbkdf2_hmac('sha256', password_bytes, salt_bytes, iterations)

    # Encode derived key in base64
    hash_b64 = base64.b64encode(dk).decode('ascii').strip()

    # Format like Django's
    return f"pbkdf2_sha256${iterations}${salt}${hash_b64}"

if __name__ == "__main__":
    import getpass
    password = getpass.getpass("Enter password to hash: ")
    hashed = pbkdf2_sha256_hash(password)
    print("\nHashed password (Django format):")
    print(hashed)