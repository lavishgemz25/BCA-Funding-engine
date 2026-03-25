import os
def env(name: str, default=None):
    v=os.getenv(name)
    return v if v not in (None,"") else default

APP_BASE_URL = env("APP_BASE_URL", "http://127.0.0.1:8000")
SESSION_SECRET = env("SESSION_SECRET", "CHANGE_ME_SESSION_SECRET")
DATABASE_URL = env("DATABASE_URL", "sqlite:///./funding.db")

DEFAULT_ADMIN_EMAIL = env("DEFAULT_ADMIN_EMAIL", "admin@local")
DEFAULT_ADMIN_PASSWORD = env("DEFAULT_ADMIN_PASSWORD", "admin123!")
