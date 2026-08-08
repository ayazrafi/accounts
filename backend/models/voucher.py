from mongoengine import Document, StringField, FloatField, DateTimeField, ObjectIdField, DictField
from bson import ObjectId
from datetime import datetime

import backend.database  # ensure mongoengine.connect() is called


VOUCHER_TYPES = ["Payment", "Receipt", "Journal", "Contra", "Sales", "Purchase", "Debit Note", "Credit Note"]


class Voucher(Document):
    voucher_no   = StringField(required=True)
    voucher_type = StringField(required=True)
    date         = DateTimeField(required=True)
    narration    = StringField(default="")
    company_id   = ObjectIdField(required=True)
    reference_type = StringField(default="")
    outstanding_amount = FloatField(default=0.0) # For Sales/Purchase vouchers
    is_fully_paid = StringField(default="No")   # "Yes" | "No"
    created_at   = DateTimeField(default=datetime.utcnow)
    metadata     = DictField(default=dict)

    meta = {'collection': 'vouchers'}


class BillWiseDetail(Document):
    """Tracks which Payment/Receipt voucher is linked to which Sales/Purchase voucher or is On Account."""
    company_id     = ObjectIdField(required=True)
    voucher_id     = ObjectIdField(required=True) # The Payment/Receipt voucher
    ref_voucher_id = ObjectIdField()              # The Sales/Purchase voucher being paid (None for On Account)
    reference_type = StringField(default="Against Reference") # "Against Reference" | "On Account"
    amount         = FloatField(required=True)
    date           = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'bill_wise_detail'}





class VoucherItem(Document):
    voucher_id   = ObjectIdField(required=True)
    voucher_type = StringField()
    voucher_no   = StringField()
    date         = DateTimeField()
    ledger_id    = ObjectIdField()
    ledger_name  = StringField()
    dr_cr        = StringField()
    amount       = FloatField(default=0.0)
    narration    = StringField(default="")
    company_id   = ObjectIdField()
    created_at   = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'voucher_items'}


# ── helpers ────────────────────────────────────────────────────────────────────
def _next_voucher_no(voucher_type: str, company_id: str) -> str:
    prefix = voucher_type[:3].upper()
    vouchers = Voucher.objects.filter(voucher_type=voucher_type, company_id=ObjectId(company_id))
    max_num = 0
    import re
    for v in vouchers:
        match = re.search(r'\d+', v.voucher_no)
        if match:
            try:
                num = int(match.group())
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    count = max_num + 1
    if voucher_type == "Sales":
        return str(count)
    return f"{prefix}-{count:05d}"



# ── CRUD ───────────────────────────────────────────────────────────────────────
def create_voucher(voucher_type: str, date: str, narration: str, entries: list,
                   company_id: str = None, reference_type: str = "",
                   grand_total: float = None, invoice_items: list = None,
                   metadata: dict = None, voucher_no: str = None) -> str:
    """
    entries: [{"ledger_id": str, "ledger_name": str, "dr_cr": "Dr"|"Cr", "amount": float}]
    grand_total: if provided, stored as outstanding_amount for Sales/Purchase vouchers.
    invoice_items: list of stock item details for Sales/Purchase.
    """
    dr_total = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
    cr_total = sum(e["amount"] for e in entries if e["dr_cr"] == "Cr")
    if abs(dr_total - cr_total) > 0.01:
        raise ValueError(f"Voucher not balanced. Dr={dr_total}, Cr={cr_total}")

    if not voucher_no:
        voucher_no = _next_voucher_no(voucher_type, company_id)

    now        = datetime.utcnow()
    date_obj   = datetime.strptime(date, "%Y-%m-%d")

    cid = ObjectId(company_id) if company_id else None

    # Grand total = max(Dr, Cr) which equals the party ledger amount (both sides balance)
    _grand = grand_total if grand_total is not None else max(dr_total, cr_total)

    v = Voucher(
        voucher_no=voucher_no,
        voucher_type=voucher_type,
        date=date_obj,
        narration=narration,
        company_id=cid,
        reference_type=reference_type,
        outstanding_amount=_grand if voucher_type in ["Sales", "Purchase", "Credit Note", "Debit Note"] else 0.0,
        metadata=metadata or {}
    )
    v.save()
    vid = str(v.id)

    for e in entries:
        VoucherItem(
            voucher_id=v.id,
            voucher_type=voucher_type,
            voucher_no=voucher_no,
            date=date_obj,
            ledger_id=ObjectId(e["ledger_id"]) if e.get("ledger_id") else None,
            ledger_name=e["ledger_name"],
            dr_cr=e["dr_cr"],
            amount=float(e["amount"]),
            narration=narration,
            company_id=cid,
        ).save()

    # Save stock transactions if any
    if invoice_items and voucher_type in ["Sales", "Purchase", "Credit Note", "Debit Note"]:
        from backend.models.inventory import add_stock_transaction
        # Sales Return (Credit Note) = IN, Purchase Return (Debit Note) = OUT
        txn_type = "IN" if voucher_type in ["Purchase", "Credit Note"] else "OUT"
        for it in invoice_items:
            add_stock_transaction(
                item_id=it["item_id"],
                item_name=it["item_name"],
                txn_type=txn_type,
                qty=it["qty"],
                rate=it["rate"],
                value=it["amount"],
                voucher_id=vid,
                date=date,
                company_id=company_id,
                discount=it.get("discount", 0.0),
                scheme=it.get("scheme", 0.0),
                final_rate=it.get("final_rate", 0.0)
            )

    return vid


def get_voucher(voucher_id: str) -> dict | None:
    v = Voucher.objects(id=voucher_id).first()
    if not v:
        return None
    items = VoucherItem.objects(voucher_id=v.id)
    
    # Enrichment: Get ledger groups to identify tax ledgers
    ledger_ids = [i.ledger_id for i in items if i.ledger_id]
    from backend.models.ledger import Ledger
    ledgers = {str(l.id): l for l in Ledger.objects(id__in=ledger_ids)}
    
    from backend.models.group import Group
    group_ids = [l.group for l in ledgers.values() if l.group]
    group_map = {str(g.id): g.name for g in Group.objects(id__in=group_ids)}

    # Bill-wise linking
    links = BillWiseDetail.objects(voucher_id=v.id)
    linking = {
        "reference_type": v.reference_type or "On Account",
        "references": [
            {
                "voucher_id": str(l.ref_voucher_id) if l.ref_voucher_id else None,
                "amount": l.amount,
                "reference_type": l.reference_type
            }
            for l in links
        ]
    }

    # Identify Party (Sales: Dr, Purchase: Cr, Receipt: Cr, Payment: Dr, Credit Note: Cr, Debit Note: Dr)
    party_side = "Dr" if v.voucher_type in ["Sales", "Payment", "Debit Note"] else "Cr"
    party_item = next((i for i in items if i.dr_cr == party_side), None)

    items_list = [
        {
            "_id":         str(i.id),
            "ledger_id":   str(i.ledger_id) if i.ledger_id else "",
            "ledger_name": i.ledger_name,
            "dr_cr":       i.dr_cr,
            "amount":      i.amount,
            "group_name":  group_map.get(str(ledgers[str(i.ledger_id)].group)) if i.ledger_id and str(i.ledger_id) in ledgers else "",
            "ledger_address": ledgers[str(i.ledger_id)].address if i.ledger_id and str(i.ledger_id) in ledgers else "",
            "ledger_gst_no":  ledgers[str(i.ledger_id)].gst_no if i.ledger_id and str(i.ledger_id) in ledgers else "",
            "ledger_phone":   ledgers[str(i.ledger_id)].phone if i.ledger_id and str(i.ledger_id) in ledgers else "",
            "ledger_email":   ledgers[str(i.ledger_id)].email if i.ledger_id and str(i.ledger_id) in ledgers else "",

        }
        for i in items
    ]

    return {
        "_id":          str(v.id),
        "voucher_no":   v.voucher_no,
        "voucher_type": v.voucher_type,
        "date":         v.date.strftime("%Y-%m-%d"),
        "narration":    v.narration,
        "company_id":   str(v.company_id) if v.company_id else "",
        "party_name":   party_item.ledger_name if party_item else "N/A",
        "party_ledger_id": str(party_item.ledger_id) if party_item and party_item.ledger_id else None,
        "amount": party_item.amount if party_item else 0.0,
        "outstanding_amount": v.outstanding_amount,
        "items": items_list,
        "entries": items_list,
        "linking": linking,
        "metadata": v.metadata or {}
    }


def list_vouchers(voucher_type = None, from_date: str = None, to_date: str = None,
                  company_id: str = None, page: int = 1, limit: int = 50) -> dict:
    q = Voucher.objects
    if company_id:
        q = q.filter(company_id=ObjectId(company_id))
    if voucher_type:
        if isinstance(voucher_type, list):
            q = q.filter(voucher_type__in=voucher_type)
        else:
            q = q.filter(voucher_type=voucher_type)
    if from_date:
        q = q.filter(date__gte=datetime.strptime(from_date, "%Y-%m-%d"))
    if to_date:
        q = q.filter(date__lte=datetime.strptime(to_date, "%Y-%m-%d"))
    
    total = q.count()
    
    q = q.order_by('-date')
    
    # Apply pagination
    if limit > 0:
        skip = (page - 1) * limit
        q = q.skip(skip).limit(limit)

    # Build a snapshot list so we can iterate q twice (once for vids, once for output)
    vouchers = list(q)
    vids = [v.id for v in vouchers]

    # Pre-fetch all voucher items in one query
    items = VoucherItem.objects(voucher_id__in=vids)

    # Accumulate both Dr and Cr totals per voucher
    dr_totals: dict = {}
    cr_totals: dict = {}
    for item in items:
        vid_str = str(item.voucher_id)
        side = (item.dr_cr or "").strip().lower()
        if side == "dr":
            dr_totals[vid_str] = dr_totals.get(vid_str, 0.0) + (item.amount or 0.0)
        elif side == "cr":
            cr_totals[vid_str] = cr_totals.get(vid_str, 0.0) + (item.amount or 0.0)

    def _grand_total(v):
        """Grand Total = the party ledger amount.
        For Sales:    party is Dr  → use outstanding_amount stored on Voucher (most reliable).
        For Purchase: party is Cr  → same.
        For other voucher types just use Dr total.
        Falls back to max(Dr, Cr) if outstanding_amount is 0.
        """
        vid_str = str(v.id)
        if v.voucher_type in ("Sales", "Purchase", "Credit Note", "Debit Note"):
            # Use the persisted outstanding_amount (= grand at creation / update time)
            # Fall back to max(Dr, Cr) in case the record was created before this fix.
            stored = v.outstanding_amount or 0.0
            if stored > 0.005:
                return stored
            return max(dr_totals.get(vid_str, 0.0), cr_totals.get(vid_str, 0.0))
        # For journal-type vouchers use Dr total (= Cr total = balanced total)
        return dr_totals.get(vid_str, 0.0)

    # Map party names and IDs for each voucher
    party_names = {}
    for item in items:
        vid_str = str(item.voucher_id)
        if vid_str in party_names: continue
        
        # Determine party side based on voucher type
        v_type = next((v.voucher_type for v in vouchers if str(v.id) == vid_str), None)
        side = "Dr" if v_type in ["Sales", "Payment", "Debit Note"] else "Cr"
        
        if item.dr_cr == side:
            party_names[vid_str] = item.ledger_name

    data = [
        {
            "_id":          str(v.id),
            "voucher_no":   v.voucher_no,
            "voucher_type": v.voucher_type,
            "date":         v.date.strftime("%Y-%m-%d"),
            "narration":    v.narration,
            "amount":       _grand_total(v),
            "party_name":   party_names.get(str(v.id), "N/A"),
            "company_id":   str(v.company_id) if v.company_id else "",
        }
        for v in vouchers
    ]
    
    return {
        "data": data,
        "total": total,
        "page": page,
        "limit": limit
    }


def delete_voucher(voucher_id: str):
    unlink_all_references(voucher_id)
    Voucher.objects(id=voucher_id).delete()
    VoucherItem.objects(voucher_id=ObjectId(voucher_id)).delete()


def update_voucher(voucher_id: str, date: str, narration: str, entries: list,
                   grand_total: float = None, invoice_items: list = None,
                   metadata: dict = None) -> None:
    """Replace voucher metadata and all its ledger entries."""
    v = Voucher.objects(id=voucher_id).first()
    if not v:
        raise ValueError("Voucher not found")

    dr_total = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
    cr_total = sum(e["amount"] for e in entries if e["dr_cr"] == "Cr")
    if abs(dr_total - cr_total) > 0.01:
        raise ValueError(f"Voucher not balanced. Dr={dr_total}, Cr={cr_total}")

    date_obj = datetime.strptime(date, "%Y-%m-%d")
    v.date      = date_obj
    v.narration = narration
    if v.voucher_type in ("Sales", "Purchase", "Credit Note", "Debit Note"):
        # Use explicit grand_total if provided; otherwise max(Dr, Cr)
        _grand = grand_total if grand_total is not None else max(dr_total, cr_total)
        v.outstanding_amount = _grand
    
    if metadata:
        v.metadata.update(metadata)
    v.save()
    
    # IMPORTANT: Unlink old references before re-linking if this was an update with linking
    # Note: If called from routes, the route should handle re-linking.
    # We unlink here to be safe.
    unlink_all_references(v.id)

    # Clear old stock transactions
    from backend.models.inventory import StockTransaction
    StockTransaction.objects(voucher_id=v.id).delete()

    # Save new stock transactions
    if invoice_items and v.voucher_type in ["Sales", "Purchase", "Credit Note", "Debit Note"]:
        from backend.models.inventory import add_stock_transaction
        txn_type = "IN" if v.voucher_type in ["Purchase", "Credit Note"] else "OUT"
        for it in invoice_items:
            add_stock_transaction(
                item_id=it["item_id"],
                item_name=it["item_name"],
                txn_type=txn_type,
                qty=it["qty"],
                rate=it["rate"],
                value=it["amount"],
                voucher_id=str(v.id),
                date=date,
                company_id=str(v.company_id),
                discount=it.get("discount", 0.0),
                scheme=it.get("scheme", 0.0),
                final_rate=it.get("final_rate", 0.0)
            )

    # Replace all items
    VoucherItem.objects(voucher_id=v.id).delete()
    for e in entries:
        VoucherItem(
            voucher_id=v.id,
            voucher_type=v.voucher_type,
            voucher_no=v.voucher_no,
            date=date_obj,
            ledger_id=ObjectId(e["ledger_id"]) if e.get("ledger_id") else None,
            ledger_name=e["ledger_name"],
            dr_cr=e["dr_cr"],
            amount=float(e["amount"]),
            narration=narration,
            company_id=v.company_id,
        ).save()


def unlink_all_references(voucher_id: str):
    """Deletes all BillWiseDetail for a voucher and restores outstanding_amount of ref vouchers."""
    v_id = ObjectId(voucher_id)
    links = BillWiseDetail.objects(voucher_id=v_id)
    for l in links:
        if l.ref_voucher_id and l.reference_type == "Against Reference":
            rv = Voucher.objects(id=l.ref_voucher_id).first()
            if rv:
                rv.outstanding_amount += l.amount
                rv.is_fully_paid = "No"
                rv.save()
    links.delete()

def link_voucher(voucher_id: str, ref_voucher_id: str, amount: float, reference_type: str = "Against Reference"):
    """
    Links a Payment/Receipt voucher to a Sales/Purchase voucher or marks it as On Account.
    Reduces the outstanding_amount of the referenced voucher if applicable.
    """
    v_id = ObjectId(voucher_id)
    v = Voucher.objects(id=v_id).first()
    if not v:
        raise ValueError("Voucher not found")
        
    rv_id = ObjectId(ref_voucher_id) if ref_voucher_id else None
    
    if reference_type == "Against Reference" and rv_id:
        rv = Voucher.objects(id=rv_id).first()
        if not rv:
            raise ValueError("Referenced voucher not found")
            
        BillWiseDetail(
            company_id=v.company_id,
            voucher_id=v_id,
            ref_voucher_id=rv_id,
            reference_type=reference_type,
            amount=amount,
            date=v.date
        ).save()
        
        new_outstanding = max(0.0, rv.outstanding_amount - amount)
        rv.outstanding_amount = new_outstanding
        rv.is_fully_paid = "Yes" if new_outstanding < 0.01 else "No"
        rv.save()
    else:
        # On Account
        BillWiseDetail(
            company_id=v.company_id,
            voucher_id=v_id,
            ref_voucher_id=None,
            reference_type="On Account",
            amount=amount,
            date=v.date
        ).save()

def get_outstanding_vouchers(company_id: str, ledger_id: str = None, vtype: str = None, include_vid: str = None) -> list:
    """Returns a list of vouchers with outstanding balance."""
    cid = ObjectId(company_id)
    
    # 1. Get vouchers with outstanding balance > 0.01
    q_out = Voucher.objects(company_id=cid, outstanding_amount__gt=0.01)
    if vtype:
        q_out = q_out.filter(voucher_type=vtype)
    
    vouchers = list(q_out)
    existing_ids = {v.id for v in vouchers}
    
    # 2. If include_vid is provided, add vouchers linked to this specific voucher
    allocated_map = {}
    if include_vid:
        from backend.models.voucher import BillWiseDetail
        links = BillWiseDetail.objects(voucher_id=ObjectId(include_vid))
        ref_vids = []
        for l in links:
            if l.ref_voucher_id:
                ref_vids.append(l.ref_voucher_id)
                allocated_map[str(l.ref_voucher_id)] = allocated_map.get(str(l.ref_voucher_id), 0.0) + l.amount
        
        if ref_vids:
            q_linked = Voucher.objects(id__in=ref_vids)
            for v in q_linked:
                if v.id not in existing_ids:
                    vouchers.append(v)
                    existing_ids.add(v.id)
    
    results = []
    for v in vouchers:
        # If ledger_id is provided, verify this voucher belongs to that ledger
        if ledger_id:
            from backend.models.voucher import VoucherItem
            # Check if any VoucherItem for this voucher matches the ledger_id
            exists = VoucherItem.objects(voucher_id=v.id, ledger_id=ObjectId(ledger_id)).first()
            if not exists:
                continue
                
        # Calculate total amount (Dr sum for Sales/Receipt, Cr sum for Purchase/Payment)
        if v.voucher_type in ["Sales", "Receipt"]:
            total_amt = sum(i.amount for i in VoucherItem.objects(voucher_id=v.id, dr_cr="Dr"))
        else:
            total_amt = sum(i.amount for i in VoucherItem.objects(voucher_id=v.id, dr_cr="Cr"))
        
        # When editing, we show (current outstanding + what was paid by this voucher)
        display_amount = v.outstanding_amount + allocated_map.get(str(v.id), 0.0)
        
        # Only show if there is actually something to adjust (or it was already adjusted by this voucher)
        if display_amount < 0.01:
            continue

        results.append({
            "_id": str(v.id),
            "voucher_no": v.voucher_no,
            "voucher_type": v.voucher_type,
            "date": v.date.strftime("%Y-%m-%d"),
            "total_amount": total_amt,
            "amount": display_amount
        })
    return results

