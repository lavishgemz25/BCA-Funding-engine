from passlib.context import CryptContext

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd.hash(p or "")

def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p or "", h)
