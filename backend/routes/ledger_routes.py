from flask import Blueprint, jsonify, request
from backend.models.ledger import (
    get_all_ledgers, get_ledger_by_id, create_ledger,
    update_ledger, delete_ledger, get_ledger_balance
)
from bson import ObjectId
from backend.routes.auth_routes import check_permission_backend

ledger_bp = Blueprint("ledger", __name__, url_prefix="/api/ledgers")


def _serialize(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


@ledger_bp.get("/")
def list_ledgers():
    if not check_permission_backend('ledger', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    company_id = request.args.get("company_id")
    return jsonify([_serialize(l) for l in get_all_ledgers(company_id=company_id)])


@ledger_bp.get("/<ledger_id>")
def get_one(ledger_id):
    if not check_permission_backend('ledger', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    doc = get_ledger_by_id(ledger_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_serialize(doc))


@ledger_bp.post("/")
def add_ledger():
    if not check_permission_backend('ledger', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    if not data.get("name") or not data.get("group"):
        return jsonify({"error": "name and group required"}), 400
    if not data.get("company_id"):
        return jsonify({"error": "company_id required"}), 400
    lid = create_ledger(data)
    return jsonify({"id": lid}), 201


@ledger_bp.put("/<ledger_id>")
def edit_ledger(ledger_id):
    if not check_permission_backend('ledger', 'update'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    update_ledger(ledger_id, data)
    return jsonify({"ok": True})


@ledger_bp.delete("/<ledger_id>")
def remove_ledger(ledger_id):
    if not check_permission_backend('ledger', 'delete'):
        return jsonify({"error": "Forbidden"}), 403
    delete_ledger(ledger_id)
    return jsonify({"ok": True})


@ledger_bp.get("/<ledger_id>/balance")
def ledger_balance(ledger_id):
    if not check_permission_backend('ledger', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    bal = get_ledger_balance(ledger_id)
    return jsonify(bal)
