from flask import Blueprint, jsonify, request
from backend.models.signature import (
    get_all_signatures, get_active_signature, create_signature, activate_signature, delete_signature
)
from backend.routes.auth_routes import check_permission_backend

signature_bp = Blueprint("signature", __name__, url_prefix="/api/signatures")


@signature_bp.get("/")
def list_sigs():
    company_id = request.args.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
    # RBAC: Check settings permission
    if not check_permission_backend('settings', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(get_all_signatures(company_id))


@signature_bp.get("/active")
def active_sig():
    company_id = request.args.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
    return jsonify(get_active_signature(company_id))


@signature_bp.post("/")
def add_sig():
    company_id = request.args.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
    if not check_permission_backend('settings', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    name = data.get("name")
    image_data = data.get("image_data")
    if not name or not image_data:
        return jsonify({"error": "name and image_data are required"}), 400
    sig_id = create_signature(company_id, name, image_data)
    return jsonify({"id": sig_id}), 201


@signature_bp.post("/<sig_id>/activate")
def select_sig(sig_id):
    company_id = request.args.get("company_id")
    if not company_id:
        return jsonify({"error": "company_id required"}), 400
    if not check_permission_backend('settings', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    activate_signature(company_id, sig_id)
    return jsonify({"ok": True})


@signature_bp.delete("/<sig_id>")
def remove_sig(sig_id):
    if not check_permission_backend('settings', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    delete_signature(sig_id)
    return jsonify({"ok": True})
