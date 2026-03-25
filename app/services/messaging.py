from typing import List, Dict
SENDER_NAME="Manuel Rivera"
COMPANY="BCA Lavish Consulting LLC"
PHONE="404-632-1071"
EMAIL="lavishgemz25@gmail.com"

LABELS={
  "fico":"FICO score","credit_score":"Credit score",
  "monthly_income":"Monthly income","monthly_debt":"Monthly debt","annual_income":"Annual income",
  "time_in_business_months":"Time in business (months)",
  "annual_revenue":"Annual revenue","avg_monthly_revenue":"Avg monthly revenue",
  "purchase_price":"Purchase price","rehab_budget":"Rehab budget","arv":"ARV",
  "market_rent":"Market rent (monthly)","section8_rent":"Section 8 rent (monthly)",
  "taxes":"Taxes (monthly)","insurance":"Insurance (monthly)","hoa":"HOA (monthly)",
  "entity_type":"Entity type","industry":"Industry",
  "address":"Property address","property_type":"Property type"
}

def pretty(fields: List[str]) -> List[str]:
    return [LABELS.get(f, f.replace('_',' ').title()) for f in fields]

def missing_message(client_name: str, missing_fields: List[str], channel: str="sms") -> Dict[str,str]:
    items=pretty(missing_fields)
    if channel=="sms":
        return {"sms": f"Hey {client_name}, to complete your funding pre-qual I still need: {', '.join(items)}. Reply with the missing items and I’ll route you to the best funding options. — {SENDER_NAME}, {COMPANY}"}
    subj="Missing items needed to complete your funding pre-qualification"
    body=f"Hi {client_name},\n\nPlease send the following to complete your funding pre-qualification:\n" + "\n".join([f"- {i}" for i in items]) + f"\n\nThanks,\n{SENDER_NAME}\n{COMPANY}\n{PHONE} | {EMAIL}"
    return {"email_subject": subj, "email_body": body}
