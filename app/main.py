from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import json
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .config import SESSION_SECRET, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
from .database import Base, engine, SessionLocal
from .models import User, Lender, Product, Submission, Decision
from .security import hash_password, verify_password
from .rules.engine import run
from .services.pdf import build_pdf
from .services.messaging import missing_message


Base.metadata.create_all(bind=engine)


def _ensure_columns():
    """Lightweight SQLite migration for new columns."""
    from sqlalchemy import text

    if not str(engine.url).startswith("sqlite"):
        return

    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(products)")).fetchall()
        names = {c[1] for c in cols}

        if "sources_json" not in names:
            conn.execute(text("ALTER TABLE products ADD COLUMN sources_json TEXT"))
        if "last_verified_at" not in names:
            conn.execute(text("ALTER TABLE products ADD COLUMN last_verified_at DATETIME"))
        if "verify_interval_days" not in names:
            conn.execute(text("ALTER TABLE products ADD COLUMN verify_interval_days INTEGER DEFAULT 30"))


app = FastAPI(title="BCA Funding Qualification Platform v7")
templates = Jinja2Templates(directory="app/templates")

# Safe static mount so app does not crash if folder is missing
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed(db: Session):
    a = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
    if not a:
        db.add(
            User(
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                is_admin=True,
            )
        )
        db.commit()

    seed_lenders = [
        {"name": "Kiavi", "website": "https://www.kiavi.com/", "geography": "GA + 49 states + DC", "categories": "real_estate", "contact_notes": "Direct lender: bridge, rental, new construction."},
        {"name": "Easy Street Capital", "website": "https://easystreetcap.com/", "geography": "GA + national", "categories": "real_estate", "contact_notes": "Direct lender: DSCR + hard money."},
        {"name": "Longhorn Investments", "website": "https://www.longhorninvestments.com/", "geography": "Atlanta / GA", "categories": "real_estate", "contact_notes": "Direct private lender: acquisition + rehab capital."},
        {"name": "Paces Funding", "website": "https://www.pacesfunding.com/", "geography": "Southeast (incl. GA)", "categories": "real_estate", "contact_notes": "Direct private lender: asset-based hard money."},
        {"name": "Fairview Commercial Lending", "website": "https://www.fairviewlending.com/", "geography": "GA", "categories": "real_estate", "contact_notes": "Direct hard money lender (GA)."},
        {"name": "RBI Private Lending", "website": "https://www.rbiprivatelending.com/", "geography": "Atlanta / GA", "categories": "real_estate", "contact_notes": "Direct hard money lender: fix & flip, construction, DSCR loans."},
        {"name": "Capital Fund 1", "website": "https://capitalfund1.com/", "geography": "GA + multi-state", "categories": "real_estate", "contact_notes": "Direct commercial bridge lender."},
        {"name": "Newfi", "website": "https://newfi.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Direct DSCR/NonQM programs (confirm current matrix)."},
        {"name": "RCN Capital", "website": "https://rcncapital.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Nationwide direct private lender (bridge, fix & flip, rental)."},
        {"name": "Lima One Capital", "website": "https://www.limaone.com/", "geography": "National (46 states per site)", "categories": "real_estate", "contact_notes": "Private lender: fix & flip, bridge, rental, construction."},
        {"name": "LendingOne", "website": "https://lendingone.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Investor loans: DSCR, fix & flip, construction, portfolio."},
        {"name": "CoreVest Finance", "website": "https://www.corevestfinance.com/", "geography": "National", "categories": "real_estate", "contact_notes": "DSCR + portfolio lending programs."},
        {"name": "Anchor Loans", "website": "https://www.anchorloans.com/", "geography": "National (multi-state)", "categories": "real_estate", "contact_notes": "Private direct lender: rehab/bridge/construction."},
        {"name": "Genesis Capital", "website": "https://genesiscapital.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Private lender: fix & flip + construction + bridge."},
        {"name": "New Silver", "website": "https://newsilver.com/", "geography": "GA + multi-state", "categories": "real_estate", "contact_notes": "Direct lender: hard money + DSCR products."},
        {"name": "Ridge Street Capital", "website": "https://www.ridgestreetcap.com/", "geography": "GA + 35+ states", "categories": "real_estate", "contact_notes": "Investment property lending (fix/flip, rentals)."},
        {"name": "BridgeWell Capital", "website": "https://www.bridgewellcapital.com/", "geography": "East/Midwest + GA", "categories": "real_estate", "contact_notes": "Private money lender (bridge, rental)."},
        {"name": "Perfecto Capital", "website": "https://perfectocapital.com/", "geography": "FL + select states", "categories": "real_estate", "contact_notes": "Private lender (residential + multifamily)."},
        {"name": "Stratton Equities", "website": "https://strattonequities.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Nationwide direct hard money lender."},
        {"name": "HouseMax Funding", "website": "https://housemaxfunding.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Asset-based private lender."},
        {"name": "EquityMax", "website": "https://equitymax.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Private money lender."},
        {"name": "Fund That Flip", "website": "https://fundthatflip.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Short-term bridge/hard money for investors."},
        {"name": "LendSimpli", "website": "https://lendsimpli.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Private lender (1-4 + small MF)."},
        {"name": "Civic Financial Services", "website": "https://civicfs.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Private lender (bridge, fix & flip, rental)."},
        {"name": "Temple View Capital", "website": "https://templeviewcapital.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Private lender (fix & flip / bridge)."},
        {"name": "Visio Lending", "website": "https://visiolending.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Rental/DSCR-focused lender (verify current matrix)."},
        {"name": "Lima One Multifamily", "website": "https://www.limaone.com/", "geography": "National", "categories": "real_estate", "contact_notes": "MF bridge/new construction—use same lender entry; keep for routing."},
        {"name": "Arixa Capital", "website": "https://www.arixacapital.com/", "geography": "Select states", "categories": "real_estate", "contact_notes": "Private lender (bridge)."},
        {"name": "Kiavi Rental", "website": "https://www.kiavi.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Rental/bridge programs."},
        {"name": "Easy Street DSCR", "website": "https://easystreetcap.com/", "geography": "National", "categories": "real_estate", "contact_notes": "DSCR products; confirm terms."},
        {"name": "Groundfloor", "website": "https://www.groundfloor.us/", "geography": "Select states", "categories": "real_estate", "contact_notes": "Real estate investor lending platform; verify direct availability by state."},
        {"name": "Kiavi Construction", "website": "https://www.kiavi.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Construction programs; confirm."},
        {"name": "Express Capital Financing", "website": "https://www.expresscapitalfinancing.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Hard money / bridge lender."},
        {"name": "Kiavi Fix & Flip", "website": "https://www.kiavi.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Fix & flip programs; confirm."},
        {"name": "Patch of Land", "website": "https://patchofland.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Private lending brand (verify current status)."},
        {"name": "CoreVest Portfolio", "website": "https://www.corevestfinance.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Portfolio/DSCR."},
        {"name": "LendingHome", "website": "https://www.lendinghome.com/", "geography": "Select states", "categories": "real_estate", "contact_notes": "Investment property financing (verify current footprint)."},
        {"name": "Rehab Financial Group", "website": "https://www.rehabfinancialgroup.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Fix & flip + rental (verify current footprint)."},
        {"name": "Park Place Finance", "website": "https://www.parkplacefinance.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Hard money lender (verify footprint)."},
        {"name": "Jet Lending", "website": "https://jetlending.com/", "geography": "Select states", "categories": "real_estate", "contact_notes": "Private lender (verify footprint)."},
        {"name": "Noble Mortgage", "website": "https://noblemortgage.com/", "geography": "Select states", "categories": "real_estate", "contact_notes": "Private lender (verify footprint)."},
        {"name": "Lima One FixNFlip", "website": "https://www.limaone.com/hard-money-fix-n-flip/", "geography": "National", "categories": "real_estate", "contact_notes": "Fix & flip product page."},
        {"name": "RCN Fix & Flip", "website": "https://rcncapital.com/loan-programs", "geography": "National", "categories": "real_estate", "contact_notes": "Fix & flip + rental programs."},
        {"name": "New Silver Georgia", "website": "https://newsilver.com/", "geography": "Georgia", "categories": "real_estate", "contact_notes": "Georgia lending page available; confirm terms."},
        {"name": "Genesis Fix & Flip", "website": "https://genesiscapital.com/loan-programs/fix-and-flip/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Fix & flip program page."},
        {"name": "Anchor Construction", "website": "https://www.anchorloans.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Construction lending (verify)."},
        {"name": "Kiavi Georgia", "website": "https://www.kiavi.com/", "geography": "Georgia", "categories": "real_estate", "contact_notes": "GA coverage."},
        {"name": "Easy Street Georgia", "website": "https://easystreetcap.com/dscr-loans-georgia/", "geography": "Georgia", "categories": "real_estate", "contact_notes": "GA DSCR page."},
        {"name": "Griffin Funding DSCR", "website": "https://griffinfunding.com/georgia-mortgage-lender/dscr-loans-georgia/", "geography": "Georgia", "categories": "real_estate", "contact_notes": "Georgia DSCR lender/program."},
        {"name": "Kiavi Bridge", "website": "https://www.kiavi.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Bridge lending."},
        {"name": "RCN Rental", "website": "https://rcncapital.com/loan-programs", "geography": "National", "categories": "real_estate", "contact_notes": "Rental loan program."},
        {"name": "LendingOne DSCR", "website": "https://lendingone.com/", "geography": "National", "categories": "real_estate", "contact_notes": "DSCR rental loans."},
        {"name": "Lima One Bridge Plus", "website": "https://www.limaone.com/bridge-loans/", "geography": "National", "categories": "real_estate", "contact_notes": "Bridge Plus product."},
        {"name": "CoreVest DSCR", "website": "https://www.corevestfinance.com/dscr-loans/", "geography": "National", "categories": "real_estate", "contact_notes": "DSCR product page."},
        {"name": "Fund That Flip Bridge", "website": "https://fundthatflip.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Bridge lending."},
        {"name": "LendSimpli Bridge", "website": "https://lendsimpli.com/", "geography": "Multi-state", "categories": "real_estate", "contact_notes": "Bridge lending."},
        {"name": "HouseMax Asset-Based", "website": "https://housemaxfunding.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Asset-based lending."},
        {"name": "Stratton Equities Bridge", "website": "https://strattonequities.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Bridge / hard money."},
        {"name": "EquityMax Bridge", "website": "https://equitymax.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Bridge / hard money."},
        {"name": "Civic Bridge", "website": "https://civicfs.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Bridge / rehab."},
        {"name": "Temple View Bridge", "website": "https://templeviewcapital.com/", "geography": "National", "categories": "real_estate", "contact_notes": "Bridge / rehab."},
        {"name": "Visio DSCR", "website": "https://visiolending.com/", "geography": "National", "categories": "real_estate", "contact_notes": "DSCR / rental."},

        {"name": "Bluevine", "website": "https://www.bluevine.com/business-loans/line-of-credit", "geography": "National", "categories": "business", "contact_notes": "LOC up to $250k (issued by partner bank)."},
        {"name": "Fundbox", "website": "https://fundbox.com/", "geography": "National", "categories": "business", "contact_notes": "LOC/term loan up to $150k."},
        {"name": "OnDeck", "website": "https://www.ondeck.com/", "geography": "National", "categories": "business", "contact_notes": "Term loans/LOC (direct lender)."},
        {"name": "National Funding", "website": "https://www.nationalfunding.com/", "geography": "National", "categories": "business", "contact_notes": "Direct business lender (working capital, equipment)."},
        {"name": "PayPal Business Loans / Working Capital", "website": "https://www.paypal.com/us/business/loans", "geography": "US", "categories": "business", "contact_notes": "PayPal merchant-based offers (eligibility via account)."},
        {"name": "Square Loans", "website": "https://squareup.com/us/en/capital", "geography": "US", "categories": "business", "contact_notes": "Square Capital offers (eligibility via Square account)."},
        {"name": "Shopify Capital", "website": "https://www.shopify.com/capital", "geography": "US/CA/UK", "categories": "business", "contact_notes": "Merchant-based offers (eligibility via Shopify)."},
        {"name": "QuickBooks Capital", "website": "https://quickbooks.intuit.com/capital/", "geography": "US", "categories": "business", "contact_notes": "Intuit offers (eligibility via QuickBooks)."},
        {"name": "Kabbage (American Express)", "website": "https://www.americanexpress.com/en-us/business/blueprint/", "geography": "US", "categories": "business", "contact_notes": "AmEx small business financing tools/products (verify current lending)."},
        {"name": "Fora Financial", "website": "https://www.forafinancial.com/", "geography": "US", "categories": "business", "contact_notes": "Small business financing (verify direct terms)."},
        {"name": "CAN Capital", "website": "https://www.cancapital.com/", "geography": "US", "categories": "business", "contact_notes": "Small business financing (verify)."},
        {"name": "Kapitus", "website": "https://kapitus.com/", "geography": "US", "categories": "business", "contact_notes": "Small business financing (verify)."},
        {"name": "Headway Capital", "website": "https://www.headwaycapital.com/", "geography": "US", "categories": "business", "contact_notes": "Business line of credit."},
        {"name": "Rapid Finance", "website": "https://www.rapidfinance.com/", "geography": "US", "categories": "business", "contact_notes": "Small business financing (verify)."},
        {"name": "Credibly", "website": "https://www.credibly.com/", "geography": "US", "categories": "business", "contact_notes": "Small business financing (verify)."},
        {"name": "Balboa Capital", "website": "https://www.balboacapital.com/", "geography": "US", "categories": "business", "contact_notes": "Equipment financing."},
        {"name": "Direct Capital", "website": "https://www.directcapital.com/", "geography": "US", "categories": "business", "contact_notes": "Equipment/working capital (verify)."},
        {"name": "Lendistry", "website": "https://lendistry.com/", "geography": "US", "categories": "business", "contact_notes": "Small business financing programs (verify)."},
        {"name": "Accion Opportunity Fund", "website": "https://aofund.org/", "geography": "US", "categories": "business", "contact_notes": "Nonprofit lender for small businesses."},
        {"name": "Camino Financial", "website": "https://www.caminofinancial.com/", "geography": "US", "categories": "business", "contact_notes": "Small business lender focusing on underserved markets (verify)."},
        {"name": "Torro", "website": "https://torro.com/", "geography": "US", "categories": "business", "contact_notes": "SMB financing platform (verify direct)."},
        {"name": "Nav Business Loans", "website": "https://www.nav.com/loans/", "geography": "US", "categories": "business", "contact_notes": "May route to partners; disable if you want direct-only."},
        {"name": "Wells Fargo Small Business", "website": "https://www.wellsfargo.com/biz/", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending (requires strong profile)."},
        {"name": "Bank of America Small Business", "website": "https://www.bankofamerica.com/smallbusiness/", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending."},
        {"name": "Chase for Business", "website": "https://www.chase.com/business", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending."},
        {"name": "Truist Small Business", "website": "https://www.truist.com/small-business", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending."},
        {"name": "U.S. Bank Business Loans", "website": "https://www.usbank.com/business-banking/business-loans-and-lines-of-credit.html", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending."},
        {"name": "PNC Small Business", "website": "https://www.pnc.com/en/small-business.html", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending."},
        {"name": "TD Bank Small Business", "website": "https://www.td.com/us/en/business-banking/small-business", "geography": "US", "categories": "business", "contact_notes": "Bank direct lending."},

        {"name": "Discover Personal Loans", "website": "https://www.discover.com/personal-loans/", "geography": "US", "categories": "personal", "contact_notes": "Personal loans (eligibility includes min income)."},
        {"name": "LendingClub", "website": "https://www.lendingclub.com/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Personal loans (verify min credit/DTI in Admin)."},
        {"name": "LightStream (Truist)", "website": "https://www.lightstream.com/apply", "geography": "US", "categories": "personal", "contact_notes": "Prime credit personal loans."},
        {"name": "SoFi", "website": "https://www.sofi.com/personal-loans/", "geography": "US", "categories": "personal", "contact_notes": "Prime-ish personal loans; verify min credit."},
        {"name": "OneMain Financial", "website": "https://www.onemainfinancial.com/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Personal loans; may serve fair credit."},
        {"name": "Avant", "website": "https://www.avant.com/", "geography": "US", "categories": "personal", "contact_notes": "Personal loans (verify)."},
        {"name": "Upgrade", "website": "https://www.upgrade.com/personal-loans/", "geography": "US", "categories": "personal", "contact_notes": "Personal loans (verify)."},
        {"name": "Happy Money", "website": "https://happymoney.com/", "geography": "US", "categories": "personal", "contact_notes": "Personal loans (verify)."},
        {"name": "Best Egg", "website": "https://www.bestegg.com/personal-loans/", "geography": "US", "categories": "personal", "contact_notes": "Loans made by partner banks; apply via Best Egg portal."},
        {"name": "PenFed Credit Union", "website": "https://www.penfed.org/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Credit union personal loans."},
        {"name": "Navy Federal Credit Union", "website": "https://www.navyfederal.org/loans-cards/personal-loans.html", "geography": "US", "categories": "personal", "contact_notes": "Membership required."},
        {"name": "USAA", "website": "https://www.usaa.com/inet/wc/bank_loan_personal_main", "geography": "US", "categories": "personal", "contact_notes": "Membership required."},
        {"name": "Upstart", "website": "https://www.upstart.com/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Marketplace model; disable if strict direct-only."},
        {"name": "Prosper", "website": "https://www.prosper.com/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Marketplace model; disable if strict direct-only."},
        {"name": "Marcus by Goldman Sachs", "website": "https://www.marcus.com/us/en/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Verify availability/eligibility."},
        {"name": "Wells Fargo Personal Loans", "website": "https://www.wellsfargo.com/personal-credit/personal-loans/", "geography": "US", "categories": "personal", "contact_notes": "Bank personal loans (existing customer rules may apply)."},
        {"name": "Chase Personal Loans", "website": "https://www.chase.com/personal/loans", "geography": "US", "categories": "personal", "contact_notes": "Bank personal loans."},
        {"name": "U.S. Bank Personal Loans", "website": "https://www.usbank.com/loans-credit-lines/personal-loans-and-lines-of-credit/personal-loans.html", "geography": "US", "categories": "personal", "contact_notes": "Bank personal loans."},
        {"name": "PNC Personal Loans", "website": "https://www.pnc.com/en/personal-banking/borrowing/personal-loans.html", "geography": "US", "categories": "personal", "contact_notes": "Bank personal loans."},
        {"name": "Truist Personal Loans", "website": "https://www.truist.com/loans/personal-loans", "geography": "US", "categories": "personal", "contact_notes": "Bank personal loans."},
    ]

    for l in seed_lenders:
        existing = db.query(Lender).filter(Lender.name == l["name"]).first()
        if not existing:
            db.add(Lender(**l, is_active=True))
    db.commit()

    def slug(s: str) -> str:
        import re
        s = s.upper()
        s = re.sub(r"[^A-Z0-9]+", "_", s).strip("_")
        return s[:45]

    def add_product(key, name, category, priority, lender_name, notes, cfg):
        if db.query(Product).filter(Product.key == key).first():
            return
        db.add(
            Product(
                key=key,
                name=name,
                category=category,
                priority=priority,
                lender_name=lender_name,
                notes=notes,
                config_json=json.dumps(cfg, indent=2),
                sources_json=json.dumps([{"type": "matrix", "url": ""}], indent=2),
                last_verified_at=datetime.utcnow(),
                verify_interval_days=30,
                is_active=True,
            )
        )

    re_lenders = db.query(Lender).filter(Lender.categories.like("%real_estate%")).all()
    pr = 10
    for l in re_lenders:
        k = f"RE_{slug(l.name)}"
        nm = l.name.lower()
        if any(t in nm for t in ["dscr", "rental", "corevest", "visio", "newfi", "lendingone"]):
            cfg = {
                "requires": ["credit_score", "arv", "market_rent", "taxes", "insurance"],
                "rules": {"min_credit": 600, "uses_dscr": True, "min_dscr": 1.00, "max_ltv": 0.80, "assumed_apr": 0.095, "approve_score": 58, "conditional_score": 38},
                "weights": {"fico": 20, "dscr": 55, "ltv": 25},
            }
            add_product(k, f"DSCR / Rental (Direct) — {l.name}", "real_estate", pr, l.name, "Edit DSCR/LTV/credit thresholds per lender matrix.", cfg)
        else:
            cfg = {
                "requires": ["purchase_price", "rehab_budget", "arv"],
                "rules": {"max_ltv_arv": 0.70, "max_ltc": 0.90, "approve_score": 55, "conditional_score": 35},
                "weights": {"ltv": 55, "ltc": 45},
            }
            add_product(k, f"Asset-Based Bridge / Rehab (Direct) — {l.name}", "real_estate", pr, l.name, "Deal-first product box; tune ARV/LTC and add credit minimum if needed.", cfg)
        pr = pr + 1 if pr < 60 else 60

    bus_lenders = db.query(Lender).filter(Lender.categories.like("%business%")).all()
    pr = 20
    for l in bus_lenders:
        k = f"BUS_{slug(l.name)}"
        cfg = {
            "requires": ["fico", "time_in_business_months", "avg_monthly_revenue"],
            "rules": {"min_fico": 600, "min_time_in_business_months": 6, "min_avg_monthly_revenue": 10000, "approve_score": 60, "conditional_score": 40, "tib_norm": 36, "revenue_norm": 300000},
            "weights": {"fico": 35, "time_in_business": 30, "revenue": 35},
        }
        add_product(k, f"Business Working Capital / LOC (Direct) — {l.name}", "business", pr, l.name, "Tune minimums per lender. Disable banks if you only want fintech.", cfg)
        pr = pr + 1 if pr < 80 else 80

    per_lenders = db.query(Lender).filter(Lender.categories.like("%personal%")).all()
    pr = 30
    for l in per_lenders:
        k = f"PER_{slug(l.name)}"
        cfg = {
            "requires": ["fico", "monthly_income", "monthly_debt"],
            "rules": {"min_fico": 600, "max_dti": 0.45, "approve_score": 60, "conditional_score": 40},
            "weights": {"fico": 70, "dti": 30},
        }
        add_product(k, f"Personal Loan (Direct) — {l.name}", "personal", pr, l.name, "Tune min FICO/DTI and exclusions per lender.", cfg)
        pr = pr + 1 if pr < 90 else 90

    db.commit()


@app.on_event("startup")
def _startup():
    _ensure_columns()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


def current_user(request: Request, db: Session):
    email = request.session.get("client_email")
    if not email:
        return None
    return db.query(User).filter(User.email == email, User.is_admin == False).first()


def current_admin(request: Request, db: Session):
    email = request.session.get("admin_email")
    if not email:
        return None
    return db.query(User).filter(User.email == email, User.is_admin == True).first()


@app.get("/", response_class=HTMLResponse)
def intake_get(request: Request, db: Session = Depends(get_db)):
    u = current_user(request, db)
    notice = None if u else "Login required to submit."
    return templates.TemplateResponse("intake.html", {"request": request, "notice": notice})


@app.get("/client/register", response_class=HTMLResponse)
def client_register_get(request: Request):
    return templates.TemplateResponse("client/register.html", {"request": request, "error": None})


@app.post("/client/register")
def client_register_post(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("client/register.html", {"request": request, "error": "Email already registered"})
    db.add(User(email=email, password_hash=hash_password(password), is_admin=False, full_name=full_name, phone=phone))
    db.commit()
    request.session["client_email"] = email
    return RedirectResponse("/client/dashboard", status_code=303)


@app.get("/client/login", response_class=HTMLResponse)
def client_login_get(request: Request):
    return templates.TemplateResponse("client/login.html", {"request": request, "error": None})


@app.post("/client/login")
def client_login_post(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == email, User.is_admin == False).first()
    if not u or not verify_password(password, u.password_hash):
        return templates.TemplateResponse("client/login.html", {"request": request, "error": "Invalid credentials"})
    request.session["client_email"] = email
    return RedirectResponse("/client/dashboard", status_code=303)


@app.get("/client/logout")
def client_logout(request: Request):
    request.session.pop("client_email", None)
    return RedirectResponse("/", status_code=303)


@app.get("/client/dashboard", response_class=HTMLResponse)
def client_dashboard(request: Request, db: Session = Depends(get_db)):
    u = current_user(request, db)
    if not u:
        return RedirectResponse("/client/login", status_code=303)

    decs = db.query(Decision).filter(Decision.user_id == u.id).order_by(Decision.created_at.desc()).limit(50).all()
    rows = []
    for d in decs:
        sub = db.query(Submission).filter(Submission.id == d.submission_id).first()
        rows.append(
            {
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M"),
                "category": sub.category if sub else "",
                "top_product": d.top_product_key,
                "status": d.top_status,
                "score": d.top_score,
                "pdf_url": f"/static/{d.pdf_path}" if d.pdf_path else None,
            }
        )
    return templates.TemplateResponse("client/dashboard.html", {"request": request, "email": u.email, "rows": rows})


@app.post("/intake")
def intake_post(
    request: Request,
    category: str = Form(...),
    client_name: str = Form(...),
    client_email: str = Form(None),
    client_phone: str = Form(None),
    fico: int = Form(None),
    monthly_income: float = Form(None),
    annual_income: float = Form(None),
    monthly_debt: float = Form(None),
    entity_type: str = Form(None),
    industry: str = Form(None),
    time_in_business_months: int = Form(None),
    annual_revenue: float = Form(None),
    avg_monthly_revenue: float = Form(None),
    address: str = Form(None),
    property_type: str = Form(None),
    purchase_price: float = Form(None),
    rehab_budget: float = Form(None),
    arv: float = Form(None),
    market_rent: float = Form(None),
    section8_rent: float = Form(None),
    taxes: float = Form(None),
    insurance: float = Form(None),
    hoa: float = Form(None),
    db: Session = Depends(get_db),
):
    u = current_user(request, db)
    if not u:
        return RedirectResponse("/client/login", status_code=303)

    payload = {
        "fico": fico,
        "credit_score": fico,
        "monthly_income": monthly_income,
        "annual_income": annual_income,
        "monthly_debt": monthly_debt,
        "entity_type": entity_type,
        "industry": industry,
        "time_in_business_months": time_in_business_months,
        "annual_revenue": annual_revenue,
        "avg_monthly_revenue": avg_monthly_revenue,
        "address": address,
        "property_type": property_type,
        "purchase_price": purchase_price,
        "rehab_budget": rehab_budget,
        "arv": arv,
        "market_rent": market_rent,
        "section8_rent": section8_rent,
        "taxes": taxes,
        "insurance": insurance,
        "hoa": hoa,
        "mgmt_pct": 0.13,
        "vacancy_pct": 0.08,
        "capex_pct": 0.05,
    }

    sub = Submission(
        user_id=u.id,
        category=category,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        payload_json=json.dumps(payload),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    top, ranking = run(db, category, payload)

    lenders = []
    for l in db.query(Lender).filter(Lender.is_active == True).all():
        cats = [c.strip() for c in (l.categories or "").split(",") if c.strip()]
        if category in cats:
            lenders.append(
                {
                    "name": l.name,
                    "website": l.website,
                    "geography": l.geography,
                    "contact_notes": l.contact_notes,
                }
            )

    if top and top.get("lender_name") and not any(x["name"] == top["lender_name"] for x in lenders):
        lenders.insert(
            0,
            {
                "name": top.get("lender_name"),
                "website": "",
                "geography": "",
                "contact_notes": "Add lender details in Admin → Lender Directory.",
            },
        )

    missing = []
    if top:
        for r in top.get("reasons", []):
            if r.startswith("Missing required fields:"):
                missing = [x.strip() for x in r.split(":", 1)[1].split(",") if x.strip()]

    pdf_rel = f"reports/submission_{sub.id}.pdf"
    pdf_path = os.path.join("app/static", pdf_rel)

    # Ensure reports folder exists before PDF build
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    build_pdf(
        pdf_path,
        {
            "category": category,
            "client_name": client_name,
            "client_email": client_email,
            "client_phone": client_phone,
        },
        top,
        ranking,
        lenders,
    )

    dec = Decision(
        submission_id=sub.id,
        user_id=u.id,
        top_product_key=top["product_key"] if top else "NONE",
        top_status=top["status"] if top else "NONE",
        top_score=top["score"] if top else 0,
        ranking_json=json.dumps(ranking),
        missing_fields_json=json.dumps(missing) if missing else None,
        pdf_path=pdf_rel,
    )
    db.add(dec)
    db.commit()

    msgs = {}
    if missing:
        msgs.update(missing_message(client_name, missing, "sms"))
        msgs.update(missing_message(client_name, missing, "email"))

    matched_with = []
    for r in ranking:
        if r.get("status") in ("APPROVED", "CONDITIONAL") and r.get("lender_name"):
            lrec = db.query(Lender).filter(Lender.name == r["lender_name"]).first()
            matched_with.append(
                {
                    "product_key": r["product_key"],
                    "product_name": r["product_name"],
                    "status": r["status"],
                    "score": r["score"],
                    "lender": {
                        "name": lrec.name if lrec else r["lender_name"],
                        "website": (lrec.website if lrec else ""),
                        "geography": (lrec.geography if lrec else ""),
                        "contact_notes": (lrec.contact_notes if lrec else ""),
                    },
                }
            )

    return JSONResponse(
        {
            "submission_id": sub.id,
            "top": top,
            "matched_with": matched_with[:25],
            "ranking": ranking,
            "route_lenders": lenders[:20],
            "pdf_url": f"/static/{pdf_rel}",
            "missing_fields": missing,
            **msgs,
        }
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse("admin/home.html", {"request": request})


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_get(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@app.post("/admin/login")
def admin_login_post(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    a = db.query(User).filter(User.email == email, User.is_admin == True).first()
    if not a or not verify_password(password, a.password_hash):
        return templates.TemplateResponse("admin/login.html", {"request": request, "error": "Invalid admin credentials"})
    request.session["admin_email"] = a.email
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin_email", None)
    return RedirectResponse("/", status_code=303)


@app.get("/admin/lenders", response_class=HTMLResponse)
def lenders_list(request: Request, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    lenders = db.query(Lender).order_by(Lender.name.asc()).all()
    return templates.TemplateResponse("admin/lenders_list.html", {"request": request, "lenders": lenders})


@app.get("/admin/lenders/new", response_class=HTMLResponse)
def lenders_new(request: Request, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse("admin/lenders_edit.html", {"request": request, "l": None, "is_new": True, "action": "/admin/lenders/new"})


@app.post("/admin/lenders/new")
def lenders_new_post(
    request: Request,
    name: str = Form(...),
    website: str = Form(None),
    geography: str = Form(None),
    categories: str = Form(None),
    contact_notes: str = Form(None),
    db: Session = Depends(get_db),
):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    if db.query(Lender).filter(Lender.name == name).first():
        raise HTTPException(status_code=400, detail="Lender name exists")
    db.add(Lender(name=name, website=website, geography=geography, categories=categories, contact_notes=contact_notes, is_active=True))
    db.commit()
    return RedirectResponse("/admin/lenders", status_code=303)


@app.get("/admin/lenders/edit/{lid}", response_class=HTMLResponse)
def lenders_edit(request: Request, lid: int, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    l = db.query(Lender).filter(Lender.id == lid).first()
    if not l:
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse("admin/lenders_edit.html", {"request": request, "l": l, "is_new": False, "action": f"/admin/lenders/edit/{lid}"})


@app.post("/admin/lenders/edit/{lid}")
def lenders_edit_post(
    request: Request,
    lid: int,
    website: str = Form(None),
    geography: str = Form(None),
    categories: str = Form(None),
    contact_notes: str = Form(None),
    db: Session = Depends(get_db),
):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    l = db.query(Lender).filter(Lender.id == lid).first()
    if not l:
        raise HTTPException(status_code=404, detail="Not found")
    l.website = website
    l.geography = geography
    l.categories = categories
    l.contact_notes = contact_notes
    db.commit()
    return RedirectResponse("/admin/lenders", status_code=303)


@app.get("/admin/lenders/toggle/{lid}")
def lenders_toggle(request: Request, lid: int, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    l = db.query(Lender).filter(Lender.id == lid).first()
    if not l:
        raise HTTPException(status_code=404, detail="Not found")
    l.is_active = not l.is_active
    db.commit()
    return RedirectResponse("/admin/lenders", status_code=303)


@app.get("/admin/products", response_class=HTMLResponse)
def products_list(request: Request, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    products = db.query(Product).order_by(Product.category.asc(), Product.priority.asc(), Product.key.asc()).all()
    now = datetime.utcnow()
    for p in products:
        interval = p.verify_interval_days or 30
        p._is_stale = (p.last_verified_at is None) or (p.last_verified_at < (now - timedelta(days=interval)))
    return templates.TemplateResponse("admin/products_list.html", {"request": request, "products": products})


@app.get("/admin/products/new", response_class=HTMLResponse)
def products_new(request: Request, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    default_cfg = json.dumps({"requires": [], "rules": {}, "weights": {}}, indent=2)
    return templates.TemplateResponse(
        "admin/products_edit.html",
        {
            "request": request,
            "p": None,
            "config_json": default_cfg,
            "sources_json": "[]",
            "last_verified_display": "—",
            "is_new": True,
            "action": "/admin/products/new",
        },
    )


@app.post("/admin/products/new")
def products_new_post(
    request: Request,
    key: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    priority: int = Form(50),
    lender_name: str = Form(None),
    notes: str = Form(None),
    config_json: str = Form(...),
    sources_json: str = Form(None),
    verify_interval_days: int = Form(30),
    db: Session = Depends(get_db),
):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    if db.query(Product).filter(Product.key == key).first():
        raise HTTPException(status_code=400, detail="Key exists")
    cfg = json.loads(config_json)
    db.add(
        Product(
            key=key,
            name=name,
            category=category,
            priority=priority,
            lender_name=lender_name,
            notes=notes,
            config_json=json.dumps(cfg, indent=2),
            sources_json=sources_json,
            verify_interval_days=verify_interval_days,
            last_verified_at=datetime.utcnow(),
            is_active=True,
        )
    )
    db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@app.get("/admin/products/edit/{pid}", response_class=HTMLResponse)
def products_edit(request: Request, pid: int, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    p = db.query(Product).filter(Product.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    lv = p.last_verified_at.strftime("%Y-%m-%d") if p.last_verified_at else "—"
    return templates.TemplateResponse(
        "admin/products_edit.html",
        {
            "request": request,
            "p": p,
            "config_json": p.config_json,
            "sources_json": (p.sources_json or "[]"),
            "last_verified_display": lv,
            "is_new": False,
            "action": f"/admin/products/edit/{pid}",
        },
    )


@app.post("/admin/products/edit/{pid}")
def products_edit_post(
    request: Request,
    pid: int,
    name: str = Form(...),
    category: str = Form(...),
    priority: int = Form(50),
    lender_name: str = Form(None),
    notes: str = Form(None),
    config_json: str = Form(...),
    sources_json: str = Form(None),
    verify_interval_days: int = Form(30),
    db: Session = Depends(get_db),
):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    p = db.query(Product).filter(Product.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    cfg = json.loads(config_json)
    p.name = name
    p.category = category
    p.priority = priority
    p.lender_name = lender_name
    p.notes = notes
    p.config_json = json.dumps(cfg, indent=2)
    p.sources_json = sources_json
    p.verify_interval_days = verify_interval_days
    db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@app.get("/admin/products/toggle/{pid}")
def products_toggle(request: Request, pid: int, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    p = db.query(Product).filter(Product.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    p.is_active = not p.is_active
    db.commit()
    return RedirectResponse("/admin/products", status_code=303)


@app.get("/admin/products/mark-verified/{pid}")
def products_mark_verified(request: Request, pid: int, db: Session = Depends(get_db)):
    if not current_admin(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    p = db.query(Product).filter(Product.id == pid).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    p.last_verified_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(f"/admin/products/edit/{pid}", status_code=303)


@app.post("/api/missing-message")
def api_missing(payload: dict):
    name = payload.get("client_name", "there")
    fields = payload.get("missing_fields", [])
    channel = (payload.get("channel", "sms")).lower()
    if channel not in ("sms", "email"):
        raise HTTPException(status_code=400, detail="channel must be sms or email")
    return missing_message(name, fields, channel)
from pydantic import BaseModel
from typing import Optional

class IntakeRequest(BaseModel):
    category: str
    client_name: str
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    fico: Optional[int] = None
    monthly_income: Optional[float] = None
    annual_income: Optional[float] = None
    monthly_debt: Optional[float] = None
    entity_type: Optional[str] = None
    industry: Optional[str] = None
    time_in_business_months: Optional[int] = None
    annual_revenue: Optional[float] = None
    avg_monthly_revenue: Optional[float] = None
    address: Optional[str] = None
    property_type: Optional[str] = None
    purchase_price: Optional[float] = None
    rehab_budget: Optional[float] = None
    arv: Optional[float] = None
    market_rent: Optional[float] = None
    section8_rent: Optional[float] = None
    taxes: Optional[float] = None
    insurance: Optional[float] = None
    hoa: Optional[float] = None

@app.post("/api/qualify")
def api_qualify(req: IntakeRequest, db: Session = Depends(get_db)):
    payload = {
        "fico": req.fico,
        "credit_score": req.fico,
        "monthly_income": req.monthly_income,
        "annual_income": req.annual_income,
        "monthly_debt": req.monthly_debt,
        "entity_type": req.entity_type,
        "industry": req.industry,
        "time_in_business_months": req.time_in_business_months,
        "annual_revenue": req.annual_revenue,
        "avg_monthly_revenue": req.avg_monthly_revenue,
        "address": req.address,
        "property_type": req.property_type,
        "purchase_price": req.purchase_price,
        "rehab_budget": req.rehab_budget,
        "arv": req.arv,
        "market_rent": req.market_rent,
        "section8_rent": req.section8_rent,
        "taxes": req.taxes,
        "insurance": req.insurance,
        "hoa": req.hoa,
        "mgmt_pct": 0.13,
        "vacancy_pct": 0.08,
        "capex_pct": 0.05,
    }

    sub = Submission(
        user_id=None,
        category=req.category,
        client_name=req.client_name,
        client_email=req.client_email,
        client_phone=req.client_phone,
        payload_json=json.dumps(payload),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    top, ranking = run(db, req.category, payload)

    lenders = []
    for l in db.query(Lender).filter(Lender.is_active == True).all():
        cats = [c.strip() for c in (l.categories or "").split(",") if c.strip()]
        if req.category in cats:
            lenders.append(
                {
                    "name": l.name,
                    "website": l.website,
                    "geography": l.geography,
                    "contact_notes": l.contact_notes,
                }
            )

    if top and top.get("lender_name") and not any(x["name"] == top["lender_name"] for x in lenders):
        lenders.insert(
            0,
            {
                "name": top.get("lender_name"),
                "website": "",
                "geography": "",
                "contact_notes": "Add lender details in Admin → Lender Directory.",
            },
        )

    missing = []
    if top:
        for r in top.get("reasons", []):
            if isinstance(r, str) and r.startswith("Missing required fields:"):
                missing = [x.strip() for x in r.split(":", 1)[1].split(",") if x.strip()]

    pdf_rel = f"reports/submission_{sub.id}.pdf"
    pdf_path = os.path.join("app/static", pdf_rel)
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    build_pdf(
        pdf_path,
        {
            "category": req.category,
            "client_name": req.client_name,
            "client_email": req.client_email,
            "client_phone": req.client_phone,
        },
        top,
        ranking,
        lenders,
    )

    dec = Decision(
        submission_id=sub.id,
        user_id=None,
        top_product_key=top["product_key"] if top else "NONE",
        top_status=top["status"] if top else "NONE",
        top_score=top["score"] if top else 0,
        ranking_json=json.dumps(ranking),
        missing_fields_json=json.dumps(missing) if missing else None,
        pdf_path=pdf_rel,
    )
    db.add(dec)
    db.commit()

    msgs = {}
    if missing:
        msgs.update(missing_message(req.client_name, missing, "sms"))
        msgs.update(missing_message(req.client_name, missing, "email"))

    matched_with = []
    for r in ranking:
        if r.get("status") in ("APPROVED", "CONDITIONAL") and r.get("lender_name"):
            lrec = db.query(Lender).filter(Lender.name == r["lender_name"]).first()
            matched_with.append(
                {
                    "product_key": r["product_key"],
                    "product_name": r["product_name"],
                    "status": r["status"],
                    "score": r["score"],
                    "lender": {
                        "name": lrec.name if lrec else r["lender_name"],
                        "website": lrec.website if lrec else "",
                        "geography": lrec.geography if lrec else "",
                        "contact_notes": lrec.contact_notes if lrec else "",
                    },
                }
            )

    return JSONResponse(
        {
            "submission_id": sub.id,
            "top": top,
            "matched_with": matched_with[:25],
            "ranking": ranking,
            "route_lenders": lenders[:20],
            "pdf_url": f"/static/{pdf_rel}",
            "missing_fields": missing,
            **msgs,
        }
    )
