from mongoengine import Document, StringField, DateTimeField, ObjectIdField
from bson import ObjectId
from datetime import datetime

import backend.database  # ensure mongoengine.connect() is called


class Transport(Document):
    name       = StringField(required=True)
    gst_no     = StringField(default="")
    address    = StringField(default="")
    company_id = ObjectIdField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField()

    meta = {'collection': 'transports'}


# ── helpers ────────────────────────────────────────────────────────────────────
def _to_dict(t: Transport) -> dict:
    return {
        "_id":        str(t.id),
        "name":       t.name,
        "gst_no":     t.gst_no or "",
        "address":    t.address or "",
        "company_id": str(t.company_id) if t.company_id else "",
    }


# ── CRUD ───────────────────────────────────────────────────────────────────────
def get_all_transports(company_id: str = None) -> list:
    q = Transport.objects
    if company_id:
        q = q.filter(company_id=ObjectId(company_id))
    return [_to_dict(t) for t in q]


def get_transport_by_id(transport_id: str) -> dict | None:
    t = Transport.objects(id=transport_id).first()
    return _to_dict(t) if t else None


def create_transport(data: dict) -> str:
    t = Transport(
        name=data["name"],
        gst_no=data.get("gst_no", ""),
        address=data.get("address", ""),
        company_id=ObjectId(data["company_id"]) if data.get("company_id") else None,
    )
    t.save()
    return str(t.id)


def update_transport(transport_id: str, data: dict):
    t = Transport.objects(id=transport_id).first()
    if not t:
        return
    for field in ('name', 'gst_no', 'address'):
        if field in data:
            setattr(t, field, data[field])
    t.updated_at = datetime.utcnow()
    t.save()


def delete_transport(transport_id: str):
    Transport.objects(id=transport_id).delete()
