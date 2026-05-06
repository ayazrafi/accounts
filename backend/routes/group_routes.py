from flask import Blueprint, jsonify, request
from backend.models.group import (
    get_all_groups, create_group, delete_group, update_group, seed_default_groups
)
from bson import ObjectId

group_bp = Blueprint("group", __name__, url_prefix="/api/groups")


def _serialize(doc):
    doc["_id"] = str(doc["_id"])
    return doc


@group_bp.get("/")
def list_groups():
    return jsonify([_serialize(g) for g in get_all_groups()])


@group_bp.post("/")
def add_group():
    data = request.json or {}
    if not data.get("name") or not data.get("nature"):
        return jsonify({"error": "name and nature required"}), 400
    gid = create_group(data["name"], data["nature"], data.get("parent"))
    return jsonify({"id": gid}), 201


@group_bp.delete("/<group_id>")
def remove_group(group_id):
    delete_group(group_id)
    return jsonify({"ok": True})


@group_bp.put("/<group_id>")
def edit_group(group_id):
    data = request.json or {}
    if not data.get("name") or not data.get("nature"):
        return jsonify({"error": "name and nature required"}), 400
    update_group(group_id, data["name"], data["nature"], data.get("parent"))
    return jsonify({"ok": True})
