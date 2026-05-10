from flask import Blueprint, jsonify, request
from backend.models.voucher import (
    create_voucher, get_voucher, list_vouchers, delete_voucher, update_voucher, VOUCHER_TYPES
)

voucher_bp = Blueprint("voucher", __name__, url_prefix="/api/vouchers")


@voucher_bp.get("/types")
def get_types():
    return jsonify(VOUCHER_TYPES)


@voucher_bp.get("/")
def list_all():
    vtype = request.args.get("type")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    company_id = request.args.get("company_id")
    return jsonify(list_vouchers(vtype, from_date, to_date, company_id=company_id))


@voucher_bp.get("/<voucher_id>")
def get_one(voucher_id):
    doc = get_voucher(voucher_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(doc)


@voucher_bp.post("/")
def add_voucher():
    data = request.json or {}
    required = ["voucher_type", "date", "entries", "company_id"]
    for r in required:
        if not data.get(r):
            return jsonify({"error": f"{r} required"}), 400
    try:
        linking = data.get("linking")
        ref_type = linking.get("reference_type", "") if linking else ""
        
        vid = create_voucher(
            voucher_type=data["voucher_type"],
            date=data["date"],
            narration=data.get("narration", ""),
            entries=data["entries"],
            company_id=data["company_id"],
            reference_type=ref_type,
            grand_total=data.get("grand_total"),
            invoice_items=data.get("invoice_items"),
            metadata=data.get("metadata")
        )
        
        # Handle linking if provided directly to this route
        if linking:
            from backend.models.voucher import link_voucher
            for ref in linking.get("references", []):
                ref_type = ref.get("reference_type", "Against Reference")
                link_voucher(vid, ref.get("voucher_id"), float(ref["amount"]), reference_type=ref_type)
            if linking.get("reference_type") == "On Account" and not linking.get("references"):
                # Find the party entry to get the amount
                # Purchase: Cr Party, Sales: Dr Party
                side = "Cr" if data["voucher_type"] == "Purchase" else "Dr"
                party_amt = sum(e["amount"] for e in data["entries"] if e.get("dr_cr") == side)
                link_voucher(vid, None, float(party_amt), reference_type="On Account")
                
        return jsonify({"id": vid}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@voucher_bp.delete("/<voucher_id>")
def remove_voucher(voucher_id):
    delete_voucher(voucher_id)
    return jsonify({"ok": True})


@voucher_bp.put("/<voucher_id>")
def edit_voucher(voucher_id):
    data = request.json or {}
    try:
        update_voucher(
            voucher_id=voucher_id,
            date=data["date"],
            narration=data.get("narration", ""),
            entries=data["entries"],
            grand_total=data.get("grand_total"),
            invoice_items=data.get("invoice_items"),
            metadata=data.get("metadata")
        )
        # Handle re-linking
        linking = data.get("linking")
        if linking:
            from backend.models.voucher import link_voucher
            # 1. Process explicit references (Against Reference or On Account)
            for ref in linking.get("references", []):
                ref_type = ref.get("reference_type", "Against Reference")
                link_voucher(voucher_id, ref.get("voucher_id"), float(ref["amount"]), reference_type=ref_type)
            
            # 2. If reference_type is 'On Account' but no references were sent (simple on account)
            if linking.get("reference_type") == "On Account" and not linking.get("references"):
                v_type = data.get("voucher_type")
                if not v_type:
                    from backend.models.voucher import Voucher
                    v = Voucher.objects(id=voucher_id).first()
                    v_type = v.voucher_type if v else "Payment"
                
                # Payment: Dr Party, Receipt: Cr Party
                side = "Dr" if v_type == "Payment" else "Cr"
                party_amt = sum(e["amount"] for e in data["entries"] if e.get("dr_cr") == side)
                link_voucher(voucher_id, None, float(party_amt), reference_type="On Account")
        
        return jsonify({"ok": True})
    except (ValueError, KeyError, Exception) as e:
        return jsonify({"error": str(e)}), 400


@voucher_bp.get("/<voucher_id>/stock-txns")
def voucher_stock_txns(voucher_id):
    from bson import ObjectId
    from backend.models.inventory import StockTransaction, get_stock_item, get_units
    try:
        txns = StockTransaction.objects(voucher_id=ObjectId(voucher_id))
    except Exception:
        return jsonify([])
    
    # Pre-fetch units for name resolution
    try:
        units_list = get_units()
        unit_map = {str(u["_id"]): u["name"] for u in units_list}
    except Exception:
        unit_map = {}

    result = []
    for t in txns:
        item = get_stock_item(str(t.item_id))
        
        # Resolve unit name
        u_id = item["unit"] if item else ""
        u_name = unit_map.get(str(u_id), "PCS") if u_id else "PCS"
        
        result.append({
            "item_id":   str(t.item_id),
            "item_name": t.item_name or "",
            "txn_type":  t.txn_type or "",
            "qty":       t.qty or 0.0,
            "rate":      t.rate or 0.0,
            "discount":  t.discount or 0.0,
            "scheme":    t.scheme or 0.0,
            "amount":    t.value or 0.0,
            "unit":      u_name,
            "gst_rate":  item["gst_rate"] if item else 0.0,
            "hsn_sac":   item["hsn_sac"]  if item else "",
            "cgst":      item["cgst"]     if item else 0.0,
            "sgst":      item["sgst"]     if item else 0.0,
            "igst":      item["igst"]     if item else 0.0,
        })
    return jsonify(result)


@voucher_bp.post("/accounting")
def add_accounting_voucher():
    """
    Processes Payment/Receipt with strict accounting rules.
    """
    data = request.json or {}
    company_id = data.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
        
    from backend.services.accounting_engine import AccountingEngine
    from backend.models.voucher import link_voucher
    
    engine = AccountingEngine(company_id)
    res = engine.process_transaction(data)
    
    if res["status"] == "Error":
        return jsonify(res), 400
        
    # Create the voucher
    try:
        linking = data.get("linking")
        ref_type = linking.get("reference_type", "") if linking else ""

        vid = create_voucher(
            voucher_type=res["transaction_type"],
            date=data["date"],
            narration=data.get("narration", ""),
            entries=data["entries"],
            company_id=company_id,
            reference_type=ref_type
        )
        
        # Handle linking
        if linking:
            print(f"DEBUG: Processing linking with reference_type '{linking.get('reference_type')}'")
            # 1. Process explicit references (can be 'Against Reference' or 'On Account')
            for ref in linking.get("references", []):
                ref_type = ref.get("reference_type", "Against Reference")
                link_voucher(vid, ref.get("voucher_id"), float(ref["amount"]), reference_type=ref_type)
            
            # 2. If reference_type is 'On Account' but no references were sent (simple on account)
            if linking.get("reference_type") == "On Account" and not linking.get("references"):
                # Payment: Dr Party, Receipt: Cr Party
                side = "Dr" if res["transaction_type"] == "Payment" else "Cr"
                party_amt = sum(e["amount"] for e in data["entries"] if e.get("dr_cr") == side)
                link_voucher(vid, None, float(party_amt), reference_type="On Account")
        else:
            print("DEBUG: No linking object found in data.")
                
        return jsonify({"id": vid, "status": "Valid", "transaction_type": res["transaction_type"]}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@voucher_bp.get("/outstanding")
def list_outstanding():
    from backend.models.voucher import get_outstanding_vouchers
    cid = request.args.get("company_id")
    lid = request.args.get("ledger_id")
    vt = request.args.get("type")
    inc_vid = request.args.get("include_vid")
    if not cid:
        return jsonify({"error": "company_id required"}), 400
    return jsonify(get_outstanding_vouchers(cid, lid, vtype=vt, include_vid=inc_vid))
