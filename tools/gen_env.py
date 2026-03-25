import secrets, pathlib
p=pathlib.Path(".env")
secret=secrets.token_urlsafe(32)
p.write_text(f"SESSION_SECRET={secret}\nDATABASE_URL=sqlite:///./funding.db\n", encoding="utf-8")
print("Wrote .env with SESSION_SECRET and DATABASE_URL")
