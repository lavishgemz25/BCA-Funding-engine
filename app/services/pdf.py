from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def build_pdf(path: str, submission: dict, top: dict, ranking: list, lenders: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c=canvas.Canvas(path, pagesize=letter)
    w,h=letter
    y=h-48
    c.setFont("Helvetica-Bold", 14); c.drawString(50,y,"Funding Qualification Report"); y-=18
    c.setFont("Helvetica", 10); c.drawString(50,y,f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"); y-=22
    c.setFont("Helvetica-Bold", 11); c.drawString(50,y,"Submission"); y-=14
    c.setFont("Helvetica", 9)
    c.drawString(50,y,f"Category: {submission.get('category')}"); y-=12
    c.drawString(50,y,f"Client: {submission.get('client_name')} | {submission.get('client_email','')} | {submission.get('client_phone','')}"); y-=16
    c.setFont("Helvetica-Bold", 11); c.drawString(50,y,"Top Recommendation"); y-=14
    c.setFont("Helvetica", 9)
    if top:
        c.drawString(50,y,f"{top['product_name']} ({top['product_key']}) | {top['status']} | score={top['score']} | lender={top.get('lender_name','')}")
        y-=12
        rs="; ".join(top.get("reasons",[]))[:160]
        if rs:
            c.drawString(50,y,f"Notes: {rs}"); y-=14
    y-=4
    c.setFont("Helvetica-Bold", 11); c.drawString(50,y,"Where to go (lenders)"); y-=14
    c.setFont("Helvetica", 9)
    for ln in lenders[:12]:
        line=f"{ln.get('name')} | {ln.get('geography','')} | {ln.get('website','')}"
        c.drawString(50,y,line[:120]); y-=12
        if y<90:
            c.showPage(); y=h-48; c.setFont("Helvetica",9)
    y-=4
    c.setFont("Helvetica-Bold", 11); c.drawString(50,y,"Top Ranking"); y-=14
    c.setFont("Helvetica", 8)
    for r in ranking[:14]:
        reasons="; ".join(r.get("reasons",[]))
        line=f"{r['product_name']} | {r['status']} | {r.get('lender_name','')} | score={r['score']} | {reasons}"
        c.drawString(50,y,line[:140]); y-=11
        if y<90:
            c.showPage(); y=h-48; c.setFont("Helvetica",8)
    c.save()
    return path
