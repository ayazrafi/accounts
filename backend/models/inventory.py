from mongoengine import Document, StringField, FloatField, DateTimeField, ObjectIdField
from bson import ObjectId
from datetime import datetime

import backend.database  # ensure mongoengine.connect() is called


DEFAULT_UNITS = ["PCS", "KGS", "MTR", "LTR", "BOX", "PKT", "DZN", "NOS", "SET"]

DEFAULT_STOCK_GROUPS = [
    "General", "Raw Material", "Finished Goods", "Semi-Finished",
    "Trading Goods", "Packing Material",
]


# ── Document Classes ───────────────────────────────────────────────────────────
class StockUnit(Document):
    name       = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    meta = {'collection': 'stock_units'}


class StockGroup(Document):
    name       = StringField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    meta = {'collection': 'stock_groups'}


class StockCategory(Document):
    name         = StringField(required=True)
    stock_group  = StringField(required=True)
    company_id   = ObjectIdField(required=True)
    price        = FloatField(default=0.0)
    super_net    = FloatField(default=0.0)
    net          = FloatField(default=0.0)
    dhara        = FloatField(default=0.0)
    cgst         = FloatField(default=0.0)
    sgst         = FloatField(default=0.0)
    igst         = FloatField(default=0.0)
    created_at   = DateTimeField(default=datetime.utcnow)
    meta = {'collection': 'stock_categories'}


class StockItem(Document):
    name          = StringField(required=True)
    company_id    = ObjectIdField(required=True)
    stock_group   = StringField(default="General")
    category      = StringField(default="")
    unit          = StringField(default="PCS")
    hsn_sac       = StringField(default="")
    gst_rate      = FloatField(default=0.0)
    opening_qty   = FloatField(default=0.0)
    opening_rate  = FloatField(default=0.0)
    opening_value = FloatField(default=0.0)
    price         = FloatField(default=0.0)
    super_net     = FloatField(default=0.0)
    net           = FloatField(default=0.0)
    dhara         = FloatField(default=0.0)
    cgst          = FloatField(default=0.0)
    sgst          = FloatField(default=0.0)
    igst          = FloatField(default=0.0)
    created_at    = DateTimeField(default=datetime.utcnow)
    updated_at    = DateTimeField()
    meta = {'collection': 'stock_items'}


class StockTransaction(Document):
    item_id    = ObjectIdField(required=True)
    item_name  = StringField()
    txn_type   = StringField()
    qty        = FloatField(default=0.0)
    rate       = FloatField(default=0.0)
    discount   = FloatField(default=0.0)
    scheme     = FloatField(default=0.0)
    value      = FloatField(default=0.0)
    voucher_id = ObjectIdField()
    date       = DateTimeField()
    company_id = ObjectIdField()
    created_at = DateTimeField(default=datetime.utcnow)
    meta = {'collection': 'stock_transactions'}


# ── seed ───────────────────────────────────────────────────────────────────────
def seed_defaults():
    if StockUnit.objects.count() == 0:
        for u in DEFAULT_UNITS:
            StockUnit(name=u).save()
    if StockGroup.objects.count() == 0:
        for g in DEFAULT_STOCK_GROUPS:
            StockGroup(name=g).save()


# ── Units ──────────────────────────────────────────────────────────────────────
def get_units() -> list:
    return [u.name for u in StockUnit.objects.only('name')]


def create_unit(name: str) -> str | None:
    if StockUnit.objects(name=name).first():
        return None
    u = StockUnit(name=name)
    u.save()
    return str(u.id)


# ── Stock Groups ───────────────────────────────────────────────────────────────
def get_stock_groups() -> list:
    return [{"_id": str(g.id), "name": g.name} for g in StockGroup.objects.all()]


def create_stock_group(name: str) -> str:
    g = StockGroup(name=name)
    g.save()
    return str(g.id)


# ── Stock Categories ───────────────────────────────────────────────────────────
def _cat_to_dict(c: StockCategory) -> dict:
    return {
        "_id":         str(c.id),
        "name":        c.name,
        "stock_group": c.stock_group,
        "company_id":  str(c.company_id),
        "price":       c.price or 0.0,
        "super_net":   c.super_net or 0.0,
        "net":         c.net or 0.0,
        "dhara":       c.dhara or 0.0,
        "cgst":        c.cgst or 0.0,
        "sgst":        c.sgst or 0.0,
        "igst":        c.igst or 0.0,
    }


def get_stock_categories(company_id: str = None, stock_group: str = None) -> list:
    q = StockCategory.objects
    if company_id:
        q = q.filter(company_id=ObjectId(company_id))
    if stock_group:
        q = q.filter(stock_group=stock_group)
    return [_cat_to_dict(c) for c in q]


def get_stock_category(cat_id: str) -> dict | None:
    c = StockCategory.objects(id=cat_id).first()
    return _cat_to_dict(c) if c else None


def create_stock_category(data: dict) -> str:
    from backend.models.group import Group
    from backend.models.ledger import Ledger
    
    c = StockCategory(
        name=data["name"],
        stock_group=data["stock_group"],
        company_id=ObjectId(data["company_id"]),
        price=data.get("price", 0.0),
        super_net=data.get("super_net", 0.0),
        net=data.get("net", 0.0),
        dhara=data.get("dhara", 0.0),
        cgst=data.get("cgst", 0.0),
        sgst=data.get("sgst", 0.0),
        igst=data.get("igst", 0.0),
    )
    c.save()

    # Create ledgers in "Duties & Taxes" group
    dt_group = Group.objects(name="Duties & Taxes").first()
    if dt_group:
        dt_id = dt_group.id
        cid = c.company_id
        
        tax_names = [
            (f"Sales CGST@{c.cgst:g}%", "Cr", c.cgst),
            (f"Sales SGST@{c.sgst:g}%", "Cr", c.sgst),
            (f"Sales IGST@{c.igst:g}%", "Cr", c.igst),
            (f"Purchase CGST@{c.cgst:g}%", "Dr", c.cgst),
            (f"Purchase SGST@{c.sgst:g}%", "Dr", c.sgst),
            (f"Purchase IGST@{c.igst:g}%", "Dr", c.igst),
        ]
        
        for name, btype, rate in tax_names:
            if rate <= 0: continue
            # Check if ledger already exists
            exists = Ledger.objects(name=name, company_id=cid).first()
            if not exists:
                Ledger(
                    name=name,
                    group=dt_id,
                    company_id=cid,
                    balance_type=btype,
                    tax_rate=rate
                ).save()

    return str(c.id)


def update_stock_category(cat_id: str, data: dict):
    c = StockCategory.objects(id=cat_id).first()
    if not c: return
    fields = ('name', 'stock_group', 'price', 'super_net', 'net', 'dhara', 'cgst', 'sgst', 'igst')
    for f in fields:
        if f in data:
            setattr(c, f, data[f])
    c.save()


def delete_stock_category(cat_id: str):
    StockCategory.objects(id=cat_id).delete()


# ── Stock Items ────────────────────────────────────────────────────────────────
def _item_to_dict(item: StockItem) -> dict:
    return {
        "_id":           str(item.id),
        "name":          item.name,
        "company_id":    str(item.company_id) if item.company_id else "",
        "stock_group":   item.stock_group or "",
        "category":      item.category or "",
        "unit":          item.unit or "",
        "hsn_sac":       item.hsn_sac or "",
        "gst_rate":      item.gst_rate or 0.0,
        "opening_qty":   item.opening_qty or 0.0,
        "opening_rate":  item.opening_rate or 0.0,
        "opening_value": item.opening_value or 0.0,
        "price":         item.price or 0.0,
        "super_net":     item.super_net or 0.0,
        "net":           item.net or 0.0,
        "dhara":         item.dhara or 0.0,
        "cgst":          item.cgst or 0.0,
        "sgst":          item.sgst or 0.0,
        "igst":          item.igst or 0.0,
    }


def get_stock_items(company_id: str = None) -> list:
    q = StockItem.objects
    if company_id:
        q = q.filter(company_id=ObjectId(company_id))
    return [_item_to_dict(i) for i in q]


def get_stock_item(item_id: str) -> dict | None:
    i = StockItem.objects(id=item_id).first()
    return _item_to_dict(i) if i else None


def create_stock_item(data: dict) -> str:
    item = StockItem(
        name=data["name"],
        company_id=ObjectId(data["company_id"]) if data.get("company_id") else None,
        stock_group=data.get("stock_group", "General"),
        category=data.get("category", ""),
        unit=data.get("unit", "PCS"),
        hsn_sac=data.get("hsn_sac", ""),
        gst_rate=data.get("gst_rate", 0.0),
        opening_qty=data.get("opening_qty", 0.0),
        opening_rate=data.get("opening_rate", 0.0),
        opening_value=data.get("opening_value", 0.0),
        price=data.get("price", 0.0),
        super_net=data.get("super_net", 0.0),
        net=data.get("net", 0.0),
        dhara=data.get("dhara", 0.0),
        cgst=data.get("cgst", 0.0),
        sgst=data.get("sgst", 0.0),
        igst=data.get("igst", 0.0),
    )
    item.save()
    return str(item.id)


def update_stock_item(item_id: str, data: dict):
    item = StockItem.objects(id=item_id).first()
    if not item:
        return
    for f in [
        "name", "stock_group", "category", "unit", "hsn_sac", "gst_rate",
        "opening_qty", "opening_rate", "opening_value",
        "price", "super_net", "net", "dhara", "cgst", "sgst", "igst"
    ]:
        if f in data:
            setattr(item, f, data[f])
    item.updated_at = datetime.utcnow()
    item.save()


def delete_stock_item(item_id: str):
    StockItem.objects(id=item_id).delete()


# ── Stock Balance (Qty & Value) ────────────────────────────────────────────────
def get_stock_balance(item_id: str = None, company_id: str = None) -> list:
    """Returns current stock qty, rate, value per item."""
    match = {}
    if item_id:
        match["item_id"] = ObjectId(item_id)
    if company_id:
        match["company_id"] = ObjectId(company_id)

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$item_id",
            "in_qty":    {"$sum": {"$cond": [{"$eq": ["$txn_type", "IN"]},  "$qty", 0]}},
            "out_qty":   {"$sum": {"$cond": [{"$eq": ["$txn_type", "OUT"]}, "$qty", 0]}},
            "in_value":  {"$sum": {"$cond": [{"$eq": ["$txn_type", "IN"]},  "$value", 0]}},
            "out_value": {"$sum": {"$cond": [{"$eq": ["$txn_type", "OUT"]}, "$value", 0]}},
        }}
    ]
    result = {str(r["_id"]): r for r in StockTransaction._get_collection().aggregate(pipeline)}
    items = get_stock_items(company_id=company_id) if not item_id else [get_stock_item(item_id)]
    rows = []
    for item in items:
        if not item:
            continue
        iid  = item["_id"]
        txn  = result.get(iid, {})
        in_qty   = txn.get("in_qty",   0) + item.get("opening_qty",   0)
        out_qty  = txn.get("out_qty",  0)
        in_val   = txn.get("in_value", 0) + item.get("opening_value", 0)
        out_val  = txn.get("out_value",0)
        net_qty  = in_qty  - out_qty
        net_val  = in_val  - out_val
        rate     = (net_val / net_qty) if net_qty > 0 else item.get("opening_rate", 0.0)
        rows.append({
            "item_id":  iid,
            "name":     item.get("name", ""),
            "group":    item.get("stock_group", ""),
            "unit":     item.get("unit", ""),
            "hsn_code": item.get("hsn_sac", ""),
            "gst_rate": item.get("gst_rate", 0.0),
            "qty":      net_qty,
            "rate":     round(rate, 2),
            "value":    round(net_val, 2),
        })
    return rows


def add_stock_transaction(item_id: str, item_name: str, txn_type: str,
                           qty: float, rate: float, value: float,
                           voucher_id: str, date: str, company_id: str = None,
                           discount: float = 0.0, scheme: float = 0.0):
    """txn_type: IN or OUT"""
    StockTransaction(
        item_id=ObjectId(item_id),
        item_name=item_name,
        txn_type=txn_type,
        qty=qty,
        rate=rate,
        discount=discount,
        scheme=scheme,
        value=value,
        voucher_id=ObjectId(voucher_id) if voucher_id else None,
        date=datetime.strptime(date, "%Y-%m-%d"),
        company_id=ObjectId(company_id) if company_id else None,
    ).save()

