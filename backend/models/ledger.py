from mongoengine import Document, StringField, FloatField, DateTimeField, ObjectIdField
from bson import ObjectId
from datetime import datetime

import backend.database  # ensure mongoengine.connect() is called


class Ledger(Document):
    name            = StringField(required=True)
    group           = ObjectIdField(required=True)
    company_id      = ObjectIdField(required=True)
    opening_balance = FloatField(default=0.0)
    balance_type    = StringField(default="Dr")
    tax_rate        = FloatField(default=0.0)   # % for Duties & Taxes ledgers
    phone           = StringField(default="")
    email           = StringField(default="")
    address         = StringField(default="")
    state           = StringField(default="")
    gst_no          = StringField(default="")
    
    # Bank Details
    bank_name           = StringField(default="")
    account_holder_name = StringField(default="")
    account_number      = StringField(default="")
    ifsc_code           = StringField(default="")
    branch_name         = StringField(default="")
    account_type        = StringField(default="")  # Savings / Current

    created_at      = DateTimeField(default=datetime.utcnow)
    updated_at      = DateTimeField()

    meta = {'collection': 'ledgers'}


# ── helpers ────────────────────────────────────────────────────────────────────
def _to_dict(l: Ledger) -> dict:
    return {
        "_id":             str(l.id),
        "name":            l.name,
        "group":           str(l.group) if l.group else "",
        "company_id":      str(l.company_id) if l.company_id else "",
        "opening_balance": l.opening_balance or 0.0,
        "balance_type":    l.balance_type or "Dr",
        "tax_rate":        l.tax_rate or 0.0,
        "phone":           l.phone or "",
        "email":           l.email or "",
        "address":         l.address or "",
        "state":           l.state or "",
        "bank_name":       l.bank_name or "",
        "account_holder_name": l.account_holder_name or "",
        "account_number":  l.account_number or "",
        "ifsc_code":       l.ifsc_code or "",
        "branch_name":     l.branch_name or "",
        "account_type":    l.account_type or "",
        "gst_no":          l.gst_no or "",
    }


# ── CRUD ───────────────────────────────────────────────────────────────────────
def get_all_ledgers(company_id: str = None) -> list:
    q = Ledger.objects
    if company_id:
        q = q.filter(company_id=ObjectId(company_id))
    return [_to_dict(l) for l in q]


def get_ledger_by_id(ledger_id: str) -> dict | None:
    l = Ledger.objects(id=ledger_id).first()
    return _to_dict(l) if l else None


def create_ledger(data: dict) -> str:
    l = Ledger(
        name=data["name"],
        group=ObjectId(data["group"]) if data.get("group") else None,
        company_id=ObjectId(data["company_id"]) if data.get("company_id") else None,
        opening_balance=data.get("opening_balance", 0.0),
        balance_type=data.get("balance_type", "Dr"),
        tax_rate=data.get("tax_rate", 0.0),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        address=data.get("address", ""),
        state=data.get("state", ""),
        bank_name=data.get("bank_name", ""),
        account_holder_name=data.get("account_holder_name", ""),
        account_number=data.get("account_number", ""),
        ifsc_code=data.get("ifsc_code", ""),
        branch_name=data.get("branch_name", ""),
        account_type=data.get("account_type", ""),
        gst_no=data.get("gst_no", ""),
    )
    l.save()
    return str(l.id)


def update_ledger(ledger_id: str, data: dict):
    l = Ledger.objects(id=ledger_id).first()
    if not l:
        return
    for field in ('name', 'opening_balance', 'balance_type', 'tax_rate', 'phone', 'email', 'address', 'state', 'gst_no',
                  'bank_name', 'account_holder_name', 'account_number', 'ifsc_code', 'branch_name', 'account_type'):
        if field in data:
            setattr(l, field, data[field])
    if 'group' in data and data['group']:
        l.group = ObjectId(data['group'])
    l.updated_at = datetime.utcnow()
    l.save()


def delete_ledger(ledger_id: str):
    Ledger.objects(id=ledger_id).delete()


def get_ledger_balance(ledger_id: str, as_of: datetime = None) -> dict:
    from backend.models.voucher import VoucherItem
    match = {"ledger_id": ObjectId(ledger_id) if not isinstance(ledger_id, ObjectId) else ledger_id}
    if as_of:
        match["date"] = {"$lte": as_of}
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$dr_cr", "total": {"$sum": "$amount"}}}
    ]
    result = {r["_id"]: r["total"] for r in VoucherItem._get_collection().aggregate(pipeline)}
    dr = result.get("Dr", 0.0)
    cr = result.get("Cr", 0.0)
    ledger = get_ledger_by_id(ledger_id)
    if ledger:
        ob = ledger.get("opening_balance", 0.0)
        ob_type = ledger.get("balance_type", "Dr")
        if ob_type == "Dr":
            dr += ob
        else:
            cr += ob
    net = dr - cr
    return {"Dr": dr, "Cr": cr, "net": net, "type": "Dr" if net >= 0 else "Cr", "balance": abs(net)}

