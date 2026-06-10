from flask import Blueprint, jsonify, request
from backend.models.inventory import (
    get_units, create_unit,
    get_stock_groups, create_stock_group,
    get_stock_categories, get_stock_category,
    create_stock_category, update_stock_category, delete_stock_category,
    get_stock_items, get_stock_item,
    create_stock_item, update_stock_item, delete_stock_item,
    get_stock_balance, seed_defaults
)
from backend.routes.auth_routes import check_permission_backend

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


# ── Units ──────────────────────────────────────────────────────────────────────
@inventory_bp.get("/units")
def list_units():
    return jsonify(get_units())


@inventory_bp.post("/units")
def add_unit():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    uid = create_unit(data["name"].upper())
    return jsonify({"id": uid}), 201


# ── Stock Groups ───────────────────────────────────────────────────────────────
@inventory_bp.get("/stock-groups")
def list_stock_groups():
    return jsonify(get_stock_groups())


@inventory_bp.post("/stock-groups")
def add_stock_group():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    gid = create_stock_group(data["name"])
    return jsonify({"id": gid}), 201


# ── Stock Categories ───────────────────────────────────────────────────────────
@inventory_bp.get("/stock-categories")
def list_stock_categories():
    if not check_permission_backend('item', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    company_id = request.args.get("company_id")
    stock_group = request.args.get("stock_group")
    return jsonify(get_stock_categories(company_id=company_id, stock_group=stock_group))


@inventory_bp.post("/stock-categories")
def add_stock_category():
    if not check_permission_backend('item', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    if not data.get("name") or not data.get("company_id"):
        return jsonify({"error": "name and company_id required"}), 400
    cid = create_stock_category(data)
    return jsonify({"id": cid}), 201


@inventory_bp.put("/stock-categories/<cat_id>")
def edit_stock_category(cat_id):
    if not check_permission_backend('item', 'update'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    update_stock_category(cat_id, data)
    return jsonify({"ok": True})


@inventory_bp.delete("/stock-categories/<cat_id>")
def remove_stock_category(cat_id):
    if not check_permission_backend('item', 'delete'):
        return jsonify({"error": "Forbidden"}), 403
    delete_stock_category(cat_id)
    return jsonify({"ok": True})


# ── Stock Items ────────────────────────────────────────────────────────────────
@inventory_bp.get("/items")
def list_items():
    if not check_permission_backend('item', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    company_id = request.args.get("company_id")
    return jsonify(get_stock_items(company_id=company_id))


@inventory_bp.get("/items/<item_id>")
def get_item(item_id):
    if not check_permission_backend('item', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    doc = get_stock_item(item_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(doc)


@inventory_bp.post("/items")
def add_item():
    if not check_permission_backend('item', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    if not data.get("company_id"):
        return jsonify({"error": "company_id required"}), 400
    iid = create_stock_item(data)
    return jsonify({"id": iid}), 201


@inventory_bp.put("/items/<item_id>")
def edit_item(item_id):
    if not check_permission_backend('item', 'update'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    update_stock_item(item_id, data)
    return jsonify({"ok": True})


@inventory_bp.delete("/items/<item_id>")
def remove_item(item_id):
    if not check_permission_backend('item', 'delete'):
        return jsonify({"error": "Forbidden"}), 403
    delete_stock_item(item_id)
    return jsonify({"ok": True})


# ── Stock Summary ──────────────────────────────────────────────────────────────
@inventory_bp.get("/stock-summary")
def stock_summary():
    if not check_permission_backend('item', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    item_id = request.args.get("item_id")
    company_id = request.args.get("company_id")
    rows = get_stock_balance(item_id, company_id=company_id)
    total_value = sum(r["value"] for r in rows)
    return jsonify({"rows": rows, "total_value": total_value})
