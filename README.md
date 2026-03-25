# BCA Funding Qualification Platform v10 (Direct Lenders: GA + National)

This version adds:
- Preloaded **direct-lender directory** (Georgia + National)
- More products with publicly stated thresholds where available
- Real estate routing prioritized: **asset-based first**, then **light-PG 600+**

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

Default Admin:
- admin@local / admin123!

Admin UIs:
- /admin/lenders
- /admin/products


## Verified Matrix Mode (v10)
- Each Product can store `Sources JSON` (links to lender matrices/pages)
- Each Product has `Verify Interval (days)` and `Last Verified` date
- Admin product list flags **STALE** when past interval
- Use “Mark Verified Now” on a product after you confirm the lender matrix


## Click-and-Go Launchers (v10)
- START_WINDOWS.bat
- START_MAC_LINUX.sh
- docker-compose.yml
