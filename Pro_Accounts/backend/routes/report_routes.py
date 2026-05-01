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
