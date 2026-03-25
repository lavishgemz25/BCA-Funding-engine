from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _normalize_password(p: str) -> str:
    return (p or "")[:72]

def hash_password(p: str) -> str:
    return pwd.hash(_normalize_password(p))

def verify_password(p: str, h: str) -> bool:
    return pwd.verify(_normalize_password(p), h)
