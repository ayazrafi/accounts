from flask import Blueprint, jsonify, request, send_file
import json
import io
import sys
import os
from bson import ObjectId
from datetime import datetime
from backend.models.company import get_company
from backend.models.ledger import Ledger
from backend.models.voucher import Voucher, VoucherItem, BillWiseDetail
from backend.models.inventory import StockItem, StockTransaction, StockCategory, StockGroup, StockUnit
from backend.models.signature import Signature
from backend.models.transport import Transport

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")

@settings_bp.get("/backup")
def backup_company():
    company_id = request.args.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
    
    cid = ObjectId(company_id)
    company = get_company(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    # Gather all company data
    data = {
        "metadata": {
            "backup_date": datetime.utcnow().isoformat(),
            "company_name": company.get("name"),
            "company_id": company_id
        },
        "company": company,
        "ledgers": list(Ledger.objects(company_id=cid).as_pymongo()),
        "vouchers": list(Voucher.objects(company_id=cid).as_pymongo()),
        "voucher_items": list(VoucherItem.objects(company_id=cid).as_pymongo()),
        "bill_wise_details": list(BillWiseDetail.objects(company_id=cid).as_pymongo()),
        "stock_items": list(StockItem.objects(company_id=cid).as_pymongo()),
        "stock_transactions": list(StockTransaction.objects(company_id=cid).as_pymongo()),
        "stock_categories": list(StockCategory.objects(company_id=cid).as_pymongo()),
        "signatures": list(Signature.objects(company_id=cid).as_pymongo()),
        "transports": list(Transport.objects(company_id=cid).as_pymongo()),
    }

    # Helper to convert ObjectIds and Datetimes to strings for JSON
    def json_serial(obj):
        if isinstance(obj, (datetime, ObjectId)):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    json_data = json.dumps(data, default=json_serial, indent=2)
    
    buffer = io.BytesIO(json_data.encode("utf-8"))
    filename = f"backup_{company.get('name').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/json"
    )

@settings_bp.post("/restore")
def restore_company():
    company_id = request.args.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    try:
        data = json.load(file)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON file: {str(e)}"}), 400

    target_cid = ObjectId(company_id)

    # 1. Clear existing data for this company
    Ledger.objects(company_id=target_cid).delete()
    Voucher.objects(company_id=target_cid).delete()
    VoucherItem.objects(company_id=target_cid).delete()
    BillWiseDetail.objects(company_id=target_cid).delete()
    StockItem.objects(company_id=target_cid).delete()
    StockTransaction.objects(company_id=target_cid).delete()
    StockCategory.objects(company_id=target_cid).delete()
    Signature.objects(company_id=target_cid).delete()
    Transport.objects(company_id=target_cid).delete()

    # 2. Restore data with ID mapping to allow cloning into new companies
    id_map = {} # old_id -> new_id

    def parse_base(doc):
        # Remove original ID and set new company ID
        old_id = doc.pop("_id", None)
        doc["company_id"] = target_cid
        
        # Parse dates
        for field in ["date", "created_at", "updated_at"]:
            if field in doc and isinstance(doc[field], str):
                try: doc[field] = datetime.fromisoformat(doc[field])
                except: pass
        return old_id, doc

    try:
        # Step 0: Restore company info
        backup_company_info = data.get("company")
        if backup_company_info:
            from backend.models.company import update_company
            target_co = get_company(company_id)
            if target_co and target_co.get("name"):
                backup_company_info["name"] = target_co["name"]
            update_company(company_id, backup_company_info)

        # Step A: Categories
        for sc in data.get("stock_categories", []):
            old_id, doc = parse_base(sc)
            new_obj = StockCategory(**doc).save()
            id_map[str(old_id)] = new_obj.id

        # Step B: Stock Items
        for si in data.get("stock_items", []):
            old_id, doc = parse_base(si)
            new_obj = StockItem(**doc).save()
            id_map[str(old_id)] = new_obj.id

        # Step C: Ledgers
        for l in data.get("ledgers", []):
            old_id, doc = parse_base(l)
            if doc.get("group"): doc["group"] = ObjectId(doc["group"])
            new_obj = Ledger(**doc).save()
            id_map[str(old_id)] = new_obj.id

        # Step D: Vouchers
        for v in data.get("vouchers", []):
            old_id, doc = parse_base(v)
            new_obj = Voucher(**doc).save()
            id_map[str(old_id)] = new_obj.id

        # Step E: Voucher Items
        for vi in data.get("voucher_items", []):
            old_id, doc = parse_base(vi)
            # Update references
            if doc.get("voucher_id"): 
                doc["voucher_id"] = id_map.get(str(doc["voucher_id"]))
            if doc.get("ledger_id"):
                doc["ledger_id"] = id_map.get(str(doc["ledger_id"]))
            VoucherItem(**doc).save()

        # Step F: Bill Wise Details
        for bwd in data.get("bill_wise_details", []):
            old_id, doc = parse_base(bwd)
            if doc.get("voucher_id"):
                doc["voucher_id"] = id_map.get(str(doc["voucher_id"]))
            if doc.get("ref_voucher_id"):
                doc["ref_voucher_id"] = id_map.get(str(doc["ref_voucher_id"]))
            BillWiseDetail(**doc).save()

        # Step G: Stock Transactions
        for st in data.get("stock_transactions", []):
            old_id, doc = parse_base(st)
            if doc.get("item_id"):
                doc["item_id"] = id_map.get(str(doc["item_id"]))
            if doc.get("voucher_id"):
                doc["voucher_id"] = id_map.get(str(doc["voucher_id"]))
            StockTransaction(**doc).save()

        # Step H: Signatures
        for s in data.get("signatures", []):
            old_id, doc = parse_base(s)
            Signature(**doc).save()

        # Step I: Transports
        for t in data.get("transports", []):
            old_id, doc = parse_base(t)
            Transport(**doc).save()

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": f"Restore failed: {str(e)}"}), 500

    return jsonify({"ok": True, "message": "Data restored successfully"})


@settings_bp.get("/db-info")
def get_db_info():
    from backend.database import MONGO_URI, DB_NAME
    from backend.mongo_manager import DATA_DIR
    import os
    return jsonify({
        "mongo_uri": MONGO_URI,
        "db_name": DB_NAME,
        "db_path": os.path.abspath(DATA_DIR),
        "flask_port": os.getenv("FLASK_PORT", "5050")
    })


@settings_bp.post("/db-path")
def set_db_path():
    data = request.json or {}
    new_path = data.get("db_path", "").strip()
    if not new_path:
        return jsonify({"error": "Path required"}), 400

    from backend.config import get_env_path
    env_file = get_env_path()

    # Read existing lines
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()

    # Update or add MONGO_DBPATH
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("MONGO_DBPATH="):
            new_lines.append(f"MONGO_DBPATH={new_path}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"MONGO_DBPATH={new_path}\n")

    # Write back
    try:
        with open(env_file, "w") as f:
            f.writelines(new_lines)
    except Exception as e:
        return jsonify({"error": f"Failed to write .env: {str(e)}"}), 500

    return jsonify({"ok": True, "message": "Database path updated. Please restart the application."})
