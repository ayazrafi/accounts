from mongoengine import Document, StringField, DateTimeField
from datetime import datetime

import backend.database  # ensure mongoengine.connect() is called


class Company(Document):
    name             = StringField(required=True)
    address          = StringField(default="")
    phone            = StringField(default="")
    email            = StringField(default="")
    fiscal_year_from = StringField(default="")
    fiscal_year_to   = StringField(default="")
    gst_no           = StringField(default="")
    pan              = StringField(default="")
    state            = StringField(default="")
    bank_name        = StringField(default="")
    ifsc_code        = StringField(default="")
    branch_name      = StringField(default="")
    account_number   = StringField(default="")
    created_at       = DateTimeField(default=datetime.utcnow)
    updated_at       = DateTimeField()

    meta = {'collection': 'companies'}


# ── helpers ────────────────────────────────────────────────────────────────────
def _to_dict(c: Company) -> dict:
    return {
        "_id":             str(c.id),
        "name":            c.name,
        "address":         c.address or "",
        "phone":           c.phone or "",
        "email":           c.email or "",
        "fiscal_year_from": c.fiscal_year_from or "",
        "fiscal_year_to":  c.fiscal_year_to or "",
        "gst_no":          c.gst_no or "",
        "pan":             c.pan or "",
        "state":           c.state or "",
        "bank_name":       c.bank_name or "",
        "ifsc_code":       c.ifsc_code or "",
        "branch_name":     c.branch_name or "",
        "account_number":  c.account_number or "",
    }


# ── CRUD ───────────────────────────────────────────────────────────────────────
def create_company(data: dict) -> str:
    from backend.database import company_data_context

    c = Company(
        name=data["name"],
        address=data.get("address", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        fiscal_year_from=data.get("fiscal_year_from", ""),
        fiscal_year_to=data.get("fiscal_year_to", ""),
        gst_no=data.get("gst_no", ""),
        pan=data.get("pan", ""),
        state=data.get("state", ""),
        bank_name=data.get("bank_name", ""),
        ifsc_code=data.get("ifsc_code", ""),
        branch_name=data.get("branch_name", ""),
        account_number=data.get("account_number", ""),
    )
    c.save()
    with company_data_context(str(c.id)):
        pass
    return str(c.id)


def get_all_companies() -> list:
    return [_to_dict(c) for c in Company.objects.all()]


def get_company(company_id: str) -> dict | None:
    c = Company.objects(id=company_id).first()
    return _to_dict(c) if c else None


def update_company(company_id: str, data: dict):
    c = Company.objects(id=company_id).first()
    if not c:
        return
    for field in ('name', 'address', 'phone', 'email', 'fiscal_year_from', 'fiscal_year_to', 
                  'gst_no', 'pan', 'state', 'bank_name', 'ifsc_code', 'branch_name', 'account_number'):
        if field in data:
            setattr(c, field, data[field])
    c.updated_at = datetime.utcnow()
    c.save()


def delete_company(company_id: str):
    Company.objects(id=company_id).delete()

