from flask import Blueprint, jsonify, request
from backend.models.company import (
    create_company, get_all_companies, get_company, update_company, delete_company
)

company_bp = Blueprint("company", __name__, url_prefix="/api/companies")


@company_bp.get("/")
def list_companies():
    return jsonify(get_all_companies())


@company_bp.get("/<company_id>")
def get_one(company_id):
    doc = get_company(company_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(doc)


@company_bp.post("/")
def add_company():
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "name required"}), 400
    cid = create_company(data)
    return jsonify({"id": cid}), 201


@company_bp.put("/<company_id>")
def edit_company(company_id):
    data = request.json or {}
    update_company(company_id, data)
    return jsonify({"ok": True})


@company_bp.delete("/<company_id>")
def remove_company(company_id):
    delete_company(company_id)
    return jsonify({"ok": True})
