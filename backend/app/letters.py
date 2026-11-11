"""Complaint letter generator (DOCX). Pure templates, no model call, so it is instant and predictable.

Formal filings in Pakistan are normally in English, so the letter is English. The person can translate or
edit it. Recipients are generic on purpose: the user (or the where_to_go list) supplies the exact office.
"""
from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from .schemas import LetterRequest

_TEMPLATES = {
    "harassment_complaint": {
        "to": "The Chairperson, Inquiry Committee\n(or, where applicable, the Ombudsperson for Protection against Harassment of Women at the Workplace)",
        "subject": "Complaint of harassment at the workplace under the Protection against Harassment of Women at the Workplace Act, 2010 (as amended in 2022)",
        "relief": "I request that an inquiry be held under the Act, that interim measures be taken to protect me from retaliation, and that appropriate action be taken against the person responsible.",
        "default_basis": ["Protection against Harassment of Women at the Workplace Act, 2010 (as amended by the 2022 Amendment Act)"],
    },
    "wage_complaint": {
        "to": "The Labour Inspector / Director Labour\nLabour Department",
        "subject": "Complaint regarding non-payment or underpayment of wages",
        "relief": "I request that an inspection be carried out, that my employer be directed to pay the wages due to me at not less than the notified minimum rate, and that appropriate action be taken for non-compliance.",
        "default_basis": ["Applicable provincial Minimum Wages Act and the current minimum wage notification"],
    },
    "property_complaint": {
        "to": "The Ombudsperson\nunder the Enforcement of Women's Property Rights Act",
        "subject": "Complaint of deprivation of ownership or possession of property",
        "relief": "I request that my ownership and possession of the property be restored to me, and that the revenue officer or Deputy Commissioner be directed to give effect to the order.",
        "default_basis": ["Enforcement of Women's Property Rights Act applicable in my province or territory"],
    },
}


def build_letter(req: LetterRequest) -> bytes:
    t = _TEMPLATES[req.letter_type]
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    def para(text: str = "", bold: bool = False, align=None, space_after: int = 6):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = bold
        p.paragraph_format.space_after = Pt(space_after)
        if align is not None:
            p.alignment = align
        return p

    para(f"Date: {date.today().strftime('%d %B %Y')}", align=WD_ALIGN_PARAGRAPH.RIGHT)
    if req.city:
        para(f"Place: {req.city}", align=WD_ALIGN_PARAGRAPH.RIGHT)

    para("To,", bold=True, space_after=0)
    para(t["to"])
    para(f"Subject: {t['subject']}", bold=True)

    para("Respected Sir/Madam,")
    who = f"I, {req.complainant_name}"
    if req.complainant_cnic:
        who += f" (CNIC {req.complainant_cnic})"
    if req.complainant_address:
        who += f", resident of {req.complainant_address}"
    para(who + ", respectfully submit this complaint.")

    if req.respondent_name or req.respondent_details:
        para("Against:", bold=True, space_after=0)
        para(" ".join(x for x in [req.respondent_name, req.respondent_details] if x))

    para("Facts", bold=True, space_after=0)
    for chunk in [c.strip() for c in req.facts.split("\n") if c.strip()]:
        para(chunk)

    basis = req.legal_basis or t["default_basis"]
    para("Legal basis", bold=True, space_after=0)
    for b in basis:
        doc.add_paragraph(b, style="List Bullet")

    para("Prayer", bold=True, space_after=0)
    para(req.relief.strip() or t["relief"])

    para("Enclosures: [attach copies of documents, messages, pay slips, ownership papers, etc.]")
    para("Yours faithfully,", space_after=24)
    para(req.complainant_name, bold=True, space_after=0)

    foot = doc.add_paragraph()
    r = foot.add_run(
        "Draft prepared with Huqooq. This is legal information, not legal advice. "
        "Check the details and the correct office before filing."
    )
    r.italic = True
    r.font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
