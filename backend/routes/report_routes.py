from flask import Blueprint, jsonify, request
from backend.models.voucher import VoucherItem
from backend.models.ledger import Ledger
from backend.models.group import Group
from datetime import datetime
from bson import ObjectId

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d") if s else None


@reports_bp.get("/trial-balance")
def trial_balance():
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))
    company_id = request.args.get("company_id")

    match = {}
    if company_id:
        match["company_id"] = ObjectId(company_id)
    if from_date or to_date:
        match["date"] = {}
        if from_date:
            match["date"]["$gte"] = from_date
        if to_date:
            match["date"]["$lte"] = to_date

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"ledger_id": "$ledger_id", "ledger_name": "$ledger_name", "dr_cr": "$dr_cr"},
            "total": {"$sum": "$amount"}
        }}
    ]
    rows = list(VoucherItem._get_collection().aggregate(pipeline))

    ledger_map = {}
    for r in rows:
        lid = str(r["_id"].get("ledger_id")) if r["_id"].get("ledger_id") else ""
        lname = r["_id"]["ledger_name"]
        dr_cr = r["_id"]["dr_cr"]
        total = r["total"]
        if lid not in ledger_map:
            ledger_map[lid] = {"ledger_id": lid, "ledger_name": lname, "Dr": 0, "Cr": 0}
        ledger_map[lid][dr_cr] += total

    # Add opening balances
    for lid, entry in ledger_map.items():
        try:
            oid = ObjectId(lid) if lid else None
            doc = Ledger._get_collection().find_one({"_id": oid}) if oid else None
            if doc:
                ob = doc.get("opening_balance", 0.0)
                ob_type = doc.get("balance_type", "Dr")
                entry[ob_type] += ob
        except Exception:
            pass

    result = sorted(ledger_map.values(), key=lambda x: x["ledger_name"])
    total_dr = sum(r["Dr"] for r in result)
    total_cr = sum(r["Cr"] for r in result)
    return jsonify({"rows": result, "total_dr": total_dr, "total_cr": total_cr})


@reports_bp.get("/profit-loss")
def profit_loss():
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))
    company_id = request.args.get("company_id")

    match = {}
    if company_id:
        match["company_id"] = ObjectId(company_id)
    if from_date or to_date:
        match["date"] = {}
        if from_date:
            match["date"]["$gte"] = from_date
        if to_date:
            match["date"]["$lte"] = to_date

    pipeline = [
        {"$match": match},
        {"$lookup": {
            "from": "ledgers",
            "let": {"lid": {"$toObjectId": "$ledger_id"}},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$_id", "$$lid"]}}},
                {"$lookup": {
                    "from": "groups",
                    "localField": "group",
                    "foreignField": "_id",
                    "as": "grp"
                }}
            ],
            "as": "ledger_info"
        }},
        {"$unwind": {"path": "$ledger_info", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": {
                "nature": {"$arrayElemAt": ["$ledger_info.grp.nature", 0]},
                "group": "$ledger_info.group",
                "ledger_name": "$ledger_name",
                "dr_cr": "$dr_cr"
            },
            "total": {"$sum": "$amount"}
        }}
    ]
    rows = list(VoucherItem._get_collection().aggregate(pipeline))

    income = {}
    expense = {}
    for r in rows:
        nature = r["_id"].get("nature", "")
        lname = r["_id"].get("ledger_name", "")
        dr_cr = r["_id"].get("dr_cr", "Dr")
        amt = r["total"]
        if nature == "Income":
            income[lname] = income.get(lname, 0) + (amt if dr_cr == "Cr" else -amt)
        elif nature == "Expense":
            expense[lname] = expense.get(lname, 0) + (amt if dr_cr == "Dr" else -amt)

    total_income = sum(income.values())
    total_expense = sum(expense.values())
    net = total_income - total_expense
    return jsonify({
        "income": income,
        "expense": expense,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit" if net >= 0 else "net_loss": abs(net)
    })


@reports_bp.get("/ledger-statement/<ledger_id>")
def ledger_statement(ledger_id):
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))
    company_id = request.args.get("company_id")

    match = {"ledger_id": ObjectId(ledger_id)}
    if company_id:
        match["company_id"] = ObjectId(company_id)
    if from_date or to_date:
        match["date"] = {}
        if from_date:
            match["date"]["$gte"] = from_date
        if to_date:
            match["date"]["$lte"] = to_date

    entries = list(VoucherItem._get_collection().find(match).sort("date", 1))
    result = []
    running = 0.0
    for e in entries:
        amt = e["amount"]
        if e["dr_cr"] == "Dr":
            running += amt
        else:
            running -= amt
        result.append({
            "date": e["date"].strftime("%Y-%m-%d") if isinstance(e["date"], datetime) else e["date"],
            "voucher_type": e.get("voucher_type"),
            "voucher_no": e.get("voucher_no"),
            "narration": e.get("narration", ""),
            "dr_cr": e["dr_cr"],
            "amount": amt,
            "balance": abs(running),
            "balance_type": "Dr" if running >= 0 else "Cr"
        })
    return jsonify(result)


@reports_bp.get("/balance-sheet")
def balance_sheet():
    as_of = _parse_date(request.args.get("as_of"))
    company_id = request.args.get("company_id")

    # Aggregate ledger balances
    base_match = {}
    if company_id:
        base_match["company_id"] = ObjectId(company_id)
    if as_of:
        base_match["date"] = {"$lte": as_of}

    pipeline = []
    if base_match:
        pipeline.append({"$match": base_match})
    pipeline.append({"$group": {
        "_id": {"ledger_id": "$ledger_id", "ledger_name": "$ledger_name", "dr_cr": "$dr_cr"},
        "total": {"$sum": "$amount"}
    }})
    rows = list(VoucherItem._get_collection().aggregate(pipeline))
    ledger_map = {}
    for r in rows:
        lid = str(r["_id"].get("ledger_id")) if r["_id"].get("ledger_id") else ""
        lname = r["_id"]["ledger_name"]
        dr_cr = r["_id"]["dr_cr"]
        total = r["total"]
        if lid not in ledger_map:
            ledger_map[lid] = {"ledger_id": lid, "ledger_name": lname, "Dr": 0.0, "Cr": 0.0, "group": "", "nature": ""}
        ledger_map[lid][dr_cr] += total

    # Add opening balances + group/nature
    for lid, entry in ledger_map.items():
        try:
            oid = ObjectId(lid) if lid else None
            doc = Ledger._get_collection().find_one({"_id": oid}) if oid else None
            if doc:
                ob = doc.get("opening_balance", 0.0)
                ob_type = doc.get("balance_type", "Dr")
                entry[ob_type] += ob
                entry["group_id"] = doc.get("group")  # ObjectId
                # get nature + name from groups
                grp_oid = entry["group_id"]
                grp = Group._get_collection().find_one({"_id": grp_oid}) if grp_oid else None
                if grp:
                    entry["nature"] = grp.get("nature", "")
                    entry["group"]  = grp.get("name", "")
        except Exception:
            pass

    # Collect all groups from the DB to ensure even empty groups appear
    # Expense groups appear on Assets side (debit nature); Income groups on Liabilities side (credit nature)
    all_groups = list(Group._get_collection().find({"nature": {"$in": ["Liability", "Income", "Asset", "Expense"]}}))
    group_id_to_info = {str(g["_id"]): g for g in all_groups}

    # Build group buckets
    # Liabilities side = Liability + Income groups
    # Assets side      = Asset + Expense groups
    liab_groups = {}
    asset_groups = {}
    for g in all_groups:
        gid = str(g["_id"])
        bucket = {"group": g.get("name", ""), "nature": g.get("nature", ""), "ledgers": [], "group_total": 0.0}
        if g.get("nature") in ("Liability", "Income"):
            liab_groups[gid] = bucket
        elif g.get("nature") in ("Asset", "Expense"):
            asset_groups[gid] = bucket

    # Populate ledgers into group buckets
    ungrouped_liab = {"group": "Ungrouped", "nature": "Liability", "ledgers": [], "group_total": 0.0}
    ungrouped_asset = {"group": "Ungrouped", "nature": "Asset", "ledgers": [], "group_total": 0.0}

    for entry in ledger_map.values():
        nature = entry["nature"]
        lname = entry["ledger_name"]
        gid = str(entry.get("group_id", "")) if entry.get("group_id") else ""
        if nature in ("Liability", "Income"):
            bal = round(entry["Cr"] - entry["Dr"], 2)
            target = liab_groups.get(gid, ungrouped_liab)
            target["ledgers"].append({"ledger": lname, "balance": bal})
            target["group_total"] = round(target["group_total"] + bal, 2)
        elif nature in ("Asset", "Expense"):
            bal = round(entry["Dr"] - entry["Cr"], 2)
            target = asset_groups.get(gid, ungrouped_asset)
            target["ledgers"].append({"ledger": lname, "balance": bal})
            target["group_total"] = round(target["group_total"] + bal, 2)

    liab_list = sorted(liab_groups.values(), key=lambda x: x["group"])
    if ungrouped_liab["ledgers"]:
        liab_list.append(ungrouped_liab)

    asset_list = sorted(asset_groups.values(), key=lambda x: x["group"])
    if ungrouped_asset["ledgers"]:
        asset_list.append(ungrouped_asset)

    total_liabilities = sum(g["group_total"] for g in liab_list)
    total_assets      = sum(g["group_total"] for g in asset_list)
    return jsonify({
        "liabilities": liab_list,
        "assets": asset_list,
        "total_liabilities": round(total_liabilities, 2),
        "total_assets": round(total_assets, 2),
    })


@reports_bp.get("/gstr1")
def gstr1():
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))
    company_id = request.args.get("company_id")

    if not company_id:
        return jsonify({"error": "company_id required"}), 400

    from backend.models.voucher import Voucher, VoucherItem
    from backend.models.company import Company
    from backend.models.ledger import Ledger
    from backend.models.inventory import StockTransaction, StockItem

    # Fetch company own info
    comp = Company.objects(id=ObjectId(company_id)).first()
    comp_state = (comp.state or "").strip().lower() if comp else ""

    # Build match criteria
    match = {"company_id": ObjectId(company_id), "voucher_type": {"$in": ["Sales", "Credit Note", "Debit Note"]}}
    if from_date or to_date:
        match["date"] = {}
        if from_date:
            match["date"]["$gte"] = from_date
        if to_date:
            match["date"]["$lte"] = to_date

    vouchers = list(Voucher.objects(__raw__=match).order_by("date"))
    vids = [v.id for v in vouchers]

    # Pre-fetch all items and ledgers for context
    vitems = list(VoucherItem.objects(voucher_id__in=vids))
    ledgers_list = list(Ledger.objects(company_id=ObjectId(company_id)))
    ledger_map = {str(l.id): l for l in ledgers_list}

    # Group items by voucher
    vitems_by_voucher = {}
    for item in vitems:
        vid_str = str(item.voucher_id)
        if vid_str not in vitems_by_voucher:
            vitems_by_voucher[vid_str] = []
        vitems_by_voucher[vid_str].append(item)

    b2b = []
    b2cs = []
    b2cl = []
    cdnr = []
    cdnur = []
    doc_summary = {
        "total_invoices": 0,
        "cancelled_invoices": 0,
        "net_invoices": 0,
        "total_value": 0.0,
        "taxable_value": 0.0,
        "cgst": 0.0,
        "sgst": 0.0,
        "igst": 0.0
    }

    hsn_summary = {}

    for v in vouchers:
        vid_str = str(v.id)
        items = vitems_by_voucher.get(vid_str, [])
        if not items:
            continue

        # 1. Identify Party Ledger and Tax/Revenue Ledgers
        party_side = "Dr" if v.voucher_type in ["Sales", "Debit Note"] else "Cr"
        party_item = next((i for i in items if i.dr_cr == party_side), None)
        if not party_item:
            continue

        party_ledger = ledger_map.get(str(party_item.ledger_id))
        party_gstin = (party_ledger.gst_no or "").strip() if party_ledger else ""
        party_state = (party_ledger.state or "").strip() if party_ledger else ""
        
        # Determine if inter-state or intra-state
        is_interstate = party_state.strip().lower() != comp_state and party_state != "" and comp_state != ""

        # Calculate taxes
        cgst = 0.0
        sgst = 0.0
        igst = 0.0
        taxable_value = 0.0

        for item in items:
            if item.ledger_id == party_item.ledger_id:
                continue
            lname = (item.ledger_name or "").lower()
            if "cgst" in lname:
                cgst += item.amount
            elif "sgst" in lname:
                sgst += item.amount
            elif "igst" in lname:
                igst += item.amount
            elif item.dr_cr != party_side:
                # This is likely a revenue ledger (Sales) or discount ledger
                # In accounting, Dr party = Cr Sales + Cr CGST + Cr SGST
                taxable_value += item.amount

        # Fallback to outstanding_amount if taxable_value is not computed
        invoice_value = max(sum(i.amount for i in items if i.dr_cr == party_side), v.outstanding_amount)
        if taxable_value == 0:
            taxable_value = invoice_value - (cgst + sgst + igst)

        doc_summary["total_invoices"] += 1
        doc_summary["net_invoices"] += 1
        doc_summary["total_value"] += invoice_value
        doc_summary["taxable_value"] += taxable_value
        doc_summary["cgst"] += cgst
        doc_summary["sgst"] += sgst
        doc_summary["igst"] += igst

        row = {
            "voucher_id": vid_str,
            "invoice_no": v.voucher_no,
            "invoice_date": v.date.strftime("%Y-%m-%d"),
            "invoice_value": round(invoice_value, 2),
            "taxable_value": round(taxable_value, 2),
            "cgst": round(cgst, 2),
            "sgst": round(sgst, 2),
            "igst": round(igst, 2),
            "receiver_name": party_item.ledger_name,
            "place_of_supply": party_state or comp.state or "Local",
            "reverse_charge": "N",
            "invoice_type": "Regular",
            "gstin": party_gstin
        }

        # Classify supplies
        if v.voucher_type == "Sales":
            if party_gstin:
                b2b.append(row)
            else:
                if is_interstate and invoice_value > 250000:
                    b2cl.append(row)
                else:
                    b2cs.append(row)
        elif v.voucher_type in ["Credit Note", "Debit Note"]:
            row["note_type"] = "C" if v.voucher_type == "Credit Note" else "D"
            if party_gstin:
                cdnr.append(row)
            else:
                cdnur.append(row)

        # 2. HSN/SAC aggregation
        txns = list(StockTransaction.objects(voucher_id=v.id))
        for txn in txns:
            item_obj = StockItem.objects(id=txn.item_id).first()
            hsn_code = (item_obj.hsn_sac or "OTHERS") if item_obj else "OTHERS"
            hsn_desc = txn.item_name or "Stock Items"
            
            gst_rate = item_obj.gst_rate if item_obj else 18.0
            uqc = "PCS" # default
            qty = txn.qty or 0.0
            val = txn.value or 0.0  # taxable value
            
            # calculate tax for this item based on invoice place of supply
            item_cgst = 0.0
            item_sgst = 0.0
            item_igst = 0.0
            if is_interstate:
                item_igst = val * gst_rate / 100
            else:
                item_cgst = val * (gst_rate / 2) / 100
                item_sgst = val * (gst_rate / 2) / 100

            key = (hsn_code, gst_rate)
            if key not in hsn_summary:
                hsn_summary[key] = {
                    "hsn_sc": hsn_code,
                    "desc": hsn_desc,
                    "uqc": uqc,
                    "qty": 0.0,
                    "val": 0.0,
                    "txval": 0.0,
                    "iamt": 0.0,
                    "camt": 0.0,
                    "samt": 0.0,
                    "csamt": 0.0
                }
            hsn_summary[key]["qty"] += qty
            hsn_summary[key]["txval"] += val
            hsn_summary[key]["val"] += val + item_cgst + item_sgst + item_igst
            hsn_summary[key]["iamt"] += item_igst
            hsn_summary[key]["camt"] += item_cgst
            hsn_summary[key]["samt"] += item_sgst

    hsn_list = []
    for k, v in hsn_summary.items():
        v["qty"] = round(v["qty"], 2)
        v["val"] = round(v["val"], 2)
        v["txval"] = round(v["txval"], 2)
        v["iamt"] = round(v["iamt"], 2)
        v["camt"] = round(v["camt"], 2)
        v["samt"] = round(v["samt"], 2)
        hsn_list.append(v)

    # Round doc summary values
    for field in ["total_value", "taxable_value", "cgst", "sgst", "igst"]:
        doc_summary[field] = round(doc_summary[field], 2)

    return jsonify({
        "b2b": b2b,
        "b2cs": b2cs,
        "b2cl": b2cl,
        "cdnr": cdnr,
        "cdnur": cdnur,
        "hsn": hsn_list,
        "doc_summary": doc_summary
    })


@reports_bp.get("/gstr3b")
def gstr3b():
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))
    company_id = request.args.get("company_id")

    if not company_id:
        return jsonify({"error": "company_id required"}), 400

    from backend.models.voucher import Voucher, VoucherItem
    from backend.models.company import Company
    from backend.models.ledger import Ledger

    # Company Context
    comp = Company.objects(id=ObjectId(company_id)).first()
    comp_state = (comp.state or "").strip().lower() if comp else ""

    # Fetch all outward (Sales, Credit Note) and inward (Purchase)
    match = {"company_id": ObjectId(company_id), "voucher_type": {"$in": ["Sales", "Purchase", "Credit Note", "Debit Note"]}}
    if from_date or to_date:
        match["date"] = {}
        if from_date:
            match["date"]["$gte"] = from_date
        if to_date:
            match["date"]["$lte"] = to_date

    vouchers = list(Voucher.objects(__raw__=match))
    vids = [v.id for v in vouchers]

    # Pre-fetch all items and ledgers
    vitems = list(VoucherItem.objects(voucher_id__in=vids))
    ledger_map = {str(l.id): l for l in Ledger.objects(company_id=ObjectId(company_id))}

    # Group items by voucher
    vitems_by_voucher = {}
    for item in vitems:
        vid_str = str(item.voucher_id)
        if vid_str not in vitems_by_voucher:
            vitems_by_voucher[vid_str] = []
        vitems_by_voucher[vid_str].append(item)

    # 3.1 Outward Taxable Supplies (Sales)
    outward_taxable = {"taxable_value": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0}
    # 4. Eligible ITC (Purchase)
    eligible_itc = {"taxable_value": 0.0, "igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0}

    for v in vouchers:
        vid_str = str(v.id)
        items = vitems_by_voucher.get(vid_str, [])
        if not items:
            continue

        # Party item
        party_side = "Dr" if v.voucher_type in ["Sales", "Debit Note"] else "Cr"
        party_item = next((i for i in items if i.dr_cr == party_side), None)
        if not party_item:
            continue

        # Calculate taxes
        cgst = 0.0
        sgst = 0.0
        igst = 0.0
        taxable_value = 0.0

        for item in items:
            if item.ledger_id == party_item.ledger_id:
                continue
            lname = (item.ledger_name or "").lower()
            if "cgst" in lname:
                cgst += item.amount
            elif "sgst" in lname:
                sgst += item.amount
            elif "igst" in lname:
                igst += item.amount
            elif item.dr_cr != party_side:
                taxable_value += item.amount

        invoice_value = max(sum(i.amount for i in items if i.dr_cr == party_side), v.outstanding_amount)
        if taxable_value == 0:
            taxable_value = invoice_value - (cgst + sgst + igst)

        # Apply sign for Credit Note/Debit Note
        multiplier = 1.0
        if v.voucher_type == "Credit Note":
            multiplier = -1.0

        if v.voucher_type in ["Sales", "Credit Note"]:
            outward_taxable["taxable_value"] += taxable_value * multiplier
            outward_taxable["cgst"] += cgst * multiplier
            outward_taxable["sgst"] += sgst * multiplier
            outward_taxable["igst"] += igst * multiplier
        elif v.voucher_type in ["Purchase", "Debit Note"]:
            # Purchase Debit Note acts as purchase return (reduction of ITC)
            p_multiplier = 1.0
            if v.voucher_type == "Debit Note":
                p_multiplier = -1.0
            eligible_itc["taxable_value"] += taxable_value * p_multiplier
            eligible_itc["cgst"] += cgst * p_multiplier
            eligible_itc["sgst"] += sgst * p_multiplier
            eligible_itc["igst"] += igst * p_multiplier

    # Round values
    for report in [outward_taxable, eligible_itc]:
        for k in report:
            report[k] = round(report[k], 2)

    return jsonify({
        "outward_taxable": outward_taxable,
        "eligible_itc": eligible_itc
    })


@reports_bp.get("/gst-summary")
def gst_summary():
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))
    company_id = request.args.get("company_id")

    if not company_id:
        return jsonify({"error": "company_id required"}), 400

    # Leverage the gstr3b logic directly
    from flask import current_app
    with current_app.test_request_context(f"/api/reports/gstr3b?company_id={company_id}&from={request.args.get('from', '')}&to={request.args.get('to', '')}"):
        resp = gstr3b()
        res_data = resp.json if hasattr(resp, "json") else resp.get_json()

    outward = res_data.get("outward_taxable", {})
    itc = res_data.get("eligible_itc", {})

    cgst_payable = max(0.0, outward.get("cgst", 0.0) - itc.get("cgst", 0.0))
    sgst_payable = max(0.0, outward.get("sgst", 0.0) - itc.get("sgst", 0.0))
    igst_payable = max(0.0, outward.get("igst", 0.0) - itc.get("igst", 0.0))

    total_output = outward.get("cgst", 0.0) + outward.get("sgst", 0.0) + outward.get("igst", 0.0)
    total_itc = itc.get("cgst", 0.0) + itc.get("sgst", 0.0) + itc.get("igst", 0.0)
    net_payable = cgst_payable + sgst_payable + igst_payable

    return jsonify({
        "output": outward,
        "itc": itc,
        "payable": {
            "cgst": round(cgst_payable, 2),
            "sgst": round(sgst_payable, 2),
            "igst": round(igst_payable, 2),
            "net": round(net_payable, 2)
        },
        "totals": {
            "output": round(total_output, 2),
            "itc": round(total_itc, 2)
        }
    })

