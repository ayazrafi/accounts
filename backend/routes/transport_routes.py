from flask import Blueprint, jsonify, request
from backend.models.transport import (
    get_all_transports, get_transport_by_id, create_transport,
    update_transport, delete_transport
)
from backend.routes.auth_routes import check_permission_backend

transport_bp = Blueprint("transport", __name__, url_prefix="/api/transports")


def _serialize(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


@transport_bp.get("/")
def list_transports():
    if not check_permission_backend('ledger', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    company_id = request.args.get("company_id")
    return jsonify([_serialize(t) for t in get_all_transports(company_id=company_id)])


@transport_bp.get("/<transport_id>")
def get_one(transport_id):
    if not check_permission_backend('ledger', 'view'):
        return jsonify({"error": "Forbidden"}), 403
    doc = get_transport_by_id(transport_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_serialize(doc))


@transport_bp.post("/")
def add_transport():
    if not check_permission_backend('ledger', 'edit'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    if not data.get("company_id"):
        return jsonify({"error": "company_id required"}), 400
    tid = create_transport(data)
    return jsonify({"id": tid}), 201


@transport_bp.put("/<transport_id>")
def edit_transport(transport_id):
    if not check_permission_backend('ledger', 'update'):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    update_transport(transport_id, data)
    return jsonify({"ok": True})


@transport_bp.delete("/<transport_id>")
def remove_transport(transport_id):
    if not check_permission_backend('ledger', 'delete'):
        return jsonify({"error": "Forbidden"}), 403
    delete_transport(transport_id)
    return jsonify({"ok": True})
