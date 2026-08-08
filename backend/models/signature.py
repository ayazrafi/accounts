from mongoengine import Document, StringField, BooleanField, DateTimeField, ObjectIdField
from bson import ObjectId
from datetime import datetime

import backend.database


class Signature(Document):
    name       = StringField(required=True)
    image_data = StringField(required=True)  # base64 encoded string
    is_active  = BooleanField(default=False)
    company_id = ObjectIdField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'signatures'}


def get_all_signatures(company_id: str) -> list:
    q = Signature.objects(company_id=ObjectId(company_id)).order_by('-created_at')
    return [
        {
            "_id":        str(s.id),
            "name":       s.name,
            "image_data": s.image_data,
            "is_active":  s.is_active,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else ""
        }
        for s in q
    ]


def get_active_signature(company_id: str) -> dict | None:
    s = Signature.objects(company_id=ObjectId(company_id), is_active=True).first()
    if s:
        return {
            "_id":        str(s.id),
            "name":       s.name,
            "image_data": s.image_data,
            "is_active":  s.is_active
        }
    return None


def create_signature(company_id: str, name: str, image_data: str) -> str:
    # If it is the first signature, default it to active
    is_first = Signature.objects(company_id=ObjectId(company_id)).count() == 0
    s = Signature(
        name=name,
        image_data=image_data,
        is_active=is_first,
        company_id=ObjectId(company_id)
    )
    s.save()
    return str(s.id)


def activate_signature(company_id: str, signature_id: str):
    # Deactivate all other signatures for this company
    Signature.objects(company_id=ObjectId(company_id)).update(set__is_active=False)
    # Activate selected one
    Signature.objects(id=ObjectId(signature_id)).update(set__is_active=True)


def delete_signature(signature_id: str):
    Signature.objects(id=ObjectId(signature_id)).delete()
