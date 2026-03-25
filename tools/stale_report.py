import sqlite3, json, datetime, sys, os

DB=os.getenv("DATABASE_PATH","funding.db")
if DB.startswith("sqlite:///"):
    DB=DB.replace("sqlite:///","")
conn=sqlite3.connect(DB)
cur=conn.cursor()
cur.execute("SELECT key,name,lender_name,last_verified_at,verify_interval_days FROM products")
rows=cur.fetchall()
now=datetime.datetime.utcnow()
stale=[]
for k,n,l,lv,iv in rows:
    iv=iv or 30
    if lv:
        try:
            dt=datetime.datetime.fromisoformat(lv.replace("Z",""))
        except Exception:
            dt=None
    else:
        dt=None
    if (dt is None) or (dt < (now - datetime.timedelta(days=iv))):
        stale.append((k,n,l,lv,iv))
print("STALE PRODUCTS:", len(stale))
for r in stale[:200]:
    print(r)
