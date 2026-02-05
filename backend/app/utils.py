from passlib.context import CryptContext #Manages password hashing algorithms

pwd_context = CryptContext(
    schemes=["bcrypt_sha256"], #This avoids the low-level bcrypt issues and is recommended by Passlib.
    deprecated="auto" #If a hashing algorithm becomes weak in the future, mark it as deprecated automatically.
    )

def hash_password(password: str) -> str: #It takes a plain password and return a secure hashed password.
    return pwd_context.hash(password)