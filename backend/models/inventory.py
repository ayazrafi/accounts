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
    stock_group  = ObjectIdField(required=True)
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
    stock_group   = ObjectIdField()
    category      = ObjectIdField()
    unit          = ObjectIdField()
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
    item_id     = ObjectIdField(required=True)
    item_name   = StringField()
    txn_type    = StringField() # IN or OUT
    qty         = FloatField()
    rate        = FloatField()
    discount    = FloatField(default=0.0)
    scheme      = FloatField(default=0.0)
    value       = FloatField()
    voucher_id  = ObjectIdField()
    date        = DateTimeField()
    company_id  = ObjectIdField()
    created_at  = DateTimeField(default=datetime.utcnow)
    meta = {'collection': 'stock_transactions'}


def seed_defaults():
    for uname in DEFAULT_UNITS:
        if not StockUnit.objects(name=uname).first():
            StockUnit(name=uname).save()
    for gname in DEFAULT_STOCK_GROUPS:
        if not StockGroup.objects(name=gname).first():
            StockGroup(name=gname).save()

# ── Units ──────────────────────────────────────────────────────────────────────
def get_units() -> list:
    return [{"_id": str(u.id), "name": u.name} for u in StockUnit.objects.only('id', 'name')]


def create_unit(data: any) -> str:
    name = data if isinstance(data, str) else data.get("name", "")
    u = StockUnit(name=name.upper())
    u.save()
    return str(u.id)


def delete_unit(unit_id: str):
    StockUnit.objects(id=ObjectId(unit_id)).delete()


# ── Stock Groups ───────────────────────────────────────────────────────────────
def get_stock_groups() -> list:
    return [{"_id": str(g.id), "name": g.name} for g in StockGroup.objects.all()]


def create_stock_group(data: any) -> str:
    name = data if isinstance(data, str) else data.get("name", "")
    g = StockGroup(name=name)
    g.save()
    return str(g.id)


def delete_stock_group(group_id: str):
    StockGroup.objects(id=ObjectId(group_id)).delete()


def get_stock_group(group_id: str) -> dict | None:
    g = StockGroup.objects(id=ObjectId(group_id)).first()
    return {"_id": str(g.id), "name": g.name} if g else None

# ── Stock Categories ───────────────────────────────────────────────────────────
def _cat_to_dict(c: StockCategory) -> dict:
    return {
        "_id":         str(c.id),
        "name":        c.name,
        "stock_group": str(c.stock_group) if c.stock_group else "",
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
        q = q.filter(stock_group=ObjectId(stock_group))
    return [_cat_to_dict(c) for c in q]


def get_stock_category(cat_id: str) -> dict | None:
    c = StockCategory.objects(id=ObjectId(cat_id)).first()
    return _cat_to_dict(c) if c else None


def delete_stock_category(cat_id: str):
    StockCategory.objects(id=ObjectId(cat_id)).delete()


def create_stock_category(data: dict) -> str:
    from backend.models.group import Group
    from backend.models.ledger import Ledger
    
    c = StockCategory(
        name=data["name"],
        stock_group=ObjectId(data["stock_group"]),
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
    # ... rest of create_stock_category (taxes) ...
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
            exists = Ledger.objects(name=name, company_id=cid).first()
            if not exists:
                Ledger(name=name, group=dt_id, company_id=cid, balance_type=btype, tax_rate=rate).save()

    return str(c.id)


def update_stock_category(cat_id: str, data: dict):
    c = StockCategory.objects(id=cat_id).first()
    if not c: return
    fields = ('name', 'price', 'super_net', 'net', 'dhara', 'cgst', 'sgst', 'igst')
    for f in fields:
        if f in data:
            setattr(c, f, data[f])
    if 'stock_group' in data:
        c.stock_group = ObjectId(data['stock_group'])
    c.save()


# ── Stock Items ────────────────────────────────────────────────────────────────
def _item_to_dict(item: StockItem, cat: StockCategory = None) -> dict:
    d = {
        "_id":           str(item.id),
        "name":          item.name,
        "company_id":    str(item.company_id) if item.company_id else "",
        "stock_group":   str(item.stock_group) if item.stock_group else "",
        "category":      str(item.category) if item.category else "",
        "unit":          str(item.unit) if item.unit else "",
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
    # Fallback to category defaults if item values are 0
    if not cat and item.category:
        cat = StockCategory.objects(id=item.category).first()
    
    if cat:
        for f in ["price", "super_net", "net", "dhara", "cgst", "sgst", "igst"]:
            if not d.get(f):
                d[f] = getattr(cat, f, 0.0)
        if not d.get("gst_rate"):
            # Total GST from category
            cgst = cat.cgst or 0.0
            sgst = cat.sgst or 0.0
            igst = cat.igst or 0.0
            d["gst_rate"] = (cgst + sgst) if (cgst + sgst) > 0 else igst
    return d


def get_stock_items(company_id: str = None) -> list:
    q = StockItem.objects
    if company_id:
        q = q.filter(company_id=ObjectId(company_id))
    
    # Pre-fetch categories for the items to avoid N+1 queries
    cat_ids = {i.category for i in q if i.category}
    cats_map = {str(c.id): c for c in StockCategory.objects(id__in=list(cat_ids))}
    
    return [_item_to_dict(i, cats_map.get(str(i.category))) for i in q]


def get_stock_item(item_id: str) -> dict | None:
    i = StockItem.objects(id=ObjectId(item_id)).first()
    return _item_to_dict(i) if i else None


def delete_stock_item(item_id: str):
    StockItem.objects(id=ObjectId(item_id)).delete()


def create_stock_item(data: dict) -> str:
    item = StockItem(
        name=data["name"],
        company_id=ObjectId(data["company_id"]) if data.get("company_id") else None,
        stock_group=ObjectId(data["stock_group"]) if data.get("stock_group") else None,
        category=ObjectId(data["category"]) if data.get("category") else None,
        unit=ObjectId(data["unit"]) if data.get("unit") else None,
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
    if not item: return
    for f in [
        "name", "hsn_sac", "gst_rate", "opening_qty", "opening_rate", "opening_value",
        "price", "super_net", "net", "dhara", "cgst", "sgst", "igst"
    ]:
        if f in data: setattr(item, f, data[f])
    
    if "stock_group" in data: item.stock_group = ObjectId(data["stock_group"]) if data["stock_group"] else None
    if "category" in data:    item.category    = ObjectId(data["category"])    if data["category"]    else None
    if "unit" in data:        item.unit        = ObjectId(data["unit"])        if data["unit"]        else None
    
    item.updated_at = datetime.utcnow()
    item.save()


def get_stock_balance(item_id: str = None, company_id: str = None) -> list:
    """Returns current stock qty, rate, value per item."""
    match = {}
    if item_id: match["item_id"] = ObjectId(item_id)
    if company_id: match["company_id"] = ObjectId(company_id)

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
    
    # Resolving Names for Report
    items = get_stock_items(company_id=company_id) if not item_id else [get_stock_item(item_id)]
    
    groups = {str(g.id): g.name for g in StockGroup.objects.all()}
    units  = {str(u.id): u.name for u in StockUnit.objects.all()}

    rows = []
    for item in items:
        if not item: continue
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
            "group":    groups.get(item.get("stock_group", ""), ""),
            "unit":     units.get(item.get("unit", ""), ""),
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




