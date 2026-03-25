import json
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from ..models import Product

def _missing(payload: Dict[str, Any], req: List[str]) -> List[str]:
    return [f for f in req if payload.get(f) in (None, "", [])]

def _num(x):
    try: return float(x)
    except Exception: return None

def _dti(monthly_debt, monthly_income):
    inc=_num(monthly_income); debt=_num(monthly_debt) or 0
    if inc in (None,0): return None
    return debt/inc

def _dscr(rent, taxes, insurance, hoa, mgmt_pct, vacancy_pct, capex_pct, piti):
    r=_num(rent)
    if r is None or piti in (None,0): return None
    taxes=_num(taxes) or 0; insurance=_num(insurance) or 0; hoa=_num(hoa) or 0
    mg=_num(mgmt_pct) or 0; vac=_num(vacancy_pct) or 0; cap=_num(capex_pct) or 0
    noi = r - (taxes+insurance+hoa + r*mg + r*vac + r*cap)
    return noi/piti

def load_products(db: Session, category: str):
    prods=db.query(Product).filter(Product.is_active==True, Product.category==category).all()
    out=[]
    for p in prods:
        out.append({"id":p.id,"key":p.key,"name":p.name,"category":p.category,"priority":p.priority,
                    "lender_name":p.lender_name,"notes":p.notes,"config":json.loads(p.config_json)})
    return out

def evaluate(product: Dict[str,Any], payload: Dict[str,Any]) -> Tuple[str,int,List[str],Dict[str,Any]]:
    cfg=product["config"]
    req=cfg.get("requires",[])
    missing=_missing(payload, req)
    if missing:
        return "INCOMPLETE", 0, [f"Missing required fields: {', '.join(missing)}"], {"missing_fields": missing}

    rules=cfg.get("rules",{})
    weights=cfg.get("weights",{})
    reasons=[]
    score=0
    metrics={}

    fico=_num(payload.get("fico") or payload.get("credit_score"))
    dti=_dti(payload.get("monthly_debt"), payload.get("monthly_income"))
    metrics["dti"]=dti

    annual_income=_num(payload.get("annual_income"))
    if annual_income is None:
        mi=_num(payload.get("monthly_income"))
        annual_income = mi*12 if mi is not None else None
    metrics["annual_income"]=annual_income

    tib=_num(payload.get("time_in_business_months"))
    rev=_num(payload.get("annual_revenue"))
    mmr=_num(payload.get("avg_monthly_revenue"))
    metrics.update({"time_in_business_months":tib,"annual_revenue":rev,"avg_monthly_revenue":mmr})

    purchase=_num(payload.get("purchase_price")) or 0
    rehab=_num(payload.get("rehab_budget")) or 0
    arv=_num(payload.get("arv"))
    total_cost=purchase+rehab
    max_ltv_arv=_num(rules.get("max_ltv_arv") or rules.get("max_ltv"))
    loan_est=(max_ltv_arv*arv) if (max_ltv_arv and arv) else None
    ltv=(loan_est/arv) if (loan_est and arv) else None
    ltc=(loan_est/total_cost) if (loan_est and total_cost) else None
    metrics.update({"loan_amount_est":loan_est,"ltv":ltv,"ltc":ltc})

    if rules.get("uses_dscr"):
        piti=(loan_est*(_num(rules.get("assumed_apr")) or 0.10))/12 if loan_est else None
        dscr=_dscr(payload.get("section8_rent") or payload.get("market_rent"),
                   payload.get("taxes"), payload.get("insurance"), payload.get("hoa"),
                   payload.get("mgmt_pct"), payload.get("vacancy_pct"), payload.get("capex_pct"),
                   piti)
        metrics["dscr"]=dscr

    if "min_fico" in rules and fico is not None and fico < rules["min_fico"]:
        reasons.append(f"FICO below {rules['min_fico']}")
    if "min_credit" in rules and fico is not None and fico < rules["min_credit"]:
        reasons.append(f"Credit below {rules['min_credit']}")
    if "max_dti" in rules and dti is not None and dti > rules["max_dti"]:
        reasons.append(f"DTI {dti:.2f} exceeds {rules['max_dti']:.2f}")
    if "min_annual_income" in rules and annual_income is not None and annual_income < rules["min_annual_income"]:
        reasons.append(f"Annual income below {rules['min_annual_income']}")
    if "min_time_in_business_months" in rules and tib is not None and tib < rules["min_time_in_business_months"]:
        reasons.append(f"Time-in-business below {rules['min_time_in_business_months']} months")
    if "min_annual_revenue" in rules and rev is not None and rev < rules["min_annual_revenue"]:
        reasons.append(f"Annual revenue below {rules['min_annual_revenue']}")
    if "min_avg_monthly_revenue" in rules and mmr is not None and mmr < rules["min_avg_monthly_revenue"]:
        reasons.append(f"Avg monthly revenue below {rules['min_avg_monthly_revenue']}")
    if "min_dscr" in rules and metrics.get("dscr") is not None and metrics["dscr"] < rules["min_dscr"]:
        reasons.append(f"DSCR {metrics['dscr']:.2f} below {rules['min_dscr']:.2f}")
    if "max_ltv" in rules and ltv is not None and ltv > rules["max_ltv"]:
        reasons.append(f"LTV {ltv:.2f} exceeds {rules['max_ltv']:.2f}")
    if "max_ltv_arv" in rules and ltv is not None and ltv > rules["max_ltv_arv"]:
        reasons.append(f"ARV LTV {ltv:.2f} exceeds {rules['max_ltv_arv']:.2f}")
    if "max_ltc" in rules and ltc is not None and ltc > rules["max_ltc"]:
        reasons.append(f"LTC {ltc:.2f} exceeds {rules['max_ltc']:.2f}")

    if "fico" in weights and fico is not None:
        score += int(weights["fico"] * min(max((fico-550)/200,0),1))
    if "dti" in weights and dti is not None:
        score += int(weights["dti"] * (1 - min(max(dti/0.6,0),1)))
    if "annual_income" in weights and annual_income is not None:
        norm=float(rules.get("income_norm", 60000))
        score += int(weights["annual_income"] * min(max(annual_income/norm,0),1))
    if "revenue" in weights and rev is not None:
        norm=float(rules.get("revenue_norm", 250000))
        score += int(weights["revenue"] * min(max(rev/norm,0),1))
    if "time_in_business" in weights and tib is not None:
        norm=float(rules.get("tib_norm", 24))
        score += int(weights["time_in_business"] * min(max(tib/norm,0),1))
    if "dscr" in weights and metrics.get("dscr") is not None:
        score += int(weights["dscr"] * min(max((metrics["dscr"]-1.0)/0.5,0),1))
    if "ltv" in weights and ltv is not None:
        score += int(weights["ltv"] * (1 - min(max(ltv/0.85,0),1)))
    if "ltc" in weights and ltc is not None:
        score += int(weights["ltc"] * (1 - min(max(ltc/1.0,0),1)))

    approve=rules.get("approve_score",60); conditional=rules.get("conditional_score",40)
    status="APPROVED" if (not reasons and score>=approve) else ("CONDITIONAL" if score>=conditional else "DENIED")
    return status, min(score,100), reasons, metrics

def run(db: Session, category: str, payload: Dict[str,Any]):
    products=load_products(db, category)
    results=[]
    for p in products:
        status, score, reasons, metrics=evaluate(p, payload)
        results.append({"product_key":p["key"],"product_name":p["name"],"category":p["category"],"priority":p["priority"],
                        "lender_name":p.get("lender_name"),"status":status,"score":score,"reasons":reasons,"metrics":metrics})
    rank={"APPROVED":3,"CONDITIONAL":2,"INCOMPLETE":1,"DENIED":0}
    results.sort(key=lambda r:(rank[r["status"]], r["score"], -r["priority"]), reverse=True)
    return (results[0] if results else None), results
