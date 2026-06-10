from mongoengine import Document, StringField, BooleanField, DateTimeField, ReferenceField, ListField, IntField, ObjectIdField
from datetime import datetime
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

class User(Document):
    username      = StringField(required=True, unique=True)
    password_hash = StringField(required=True)
    is_active     = BooleanField(default=True)
    is_super_admin = BooleanField(default=False)
    created_at    = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'users'}

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Role(Document):
    name = StringField(required=True, unique=True)
    meta = {'collection': 'roles'}

class Permission(Document):
    role      = ReferenceField(Role, required=True)
    module    = StringField(required=True) # e.g., 'Vouchers', 'Ledgers', 'Inventory'
    can_view  = BooleanField(default=False)
    can_add   = BooleanField(default=False)
    can_edit  = BooleanField(default=False)
    can_delete = BooleanField(default=False)
    can_print = BooleanField(default=False)

    meta = {'collection': 'permissions'}

class CompanyUserMapping(Document):
    user               = ReferenceField(User, required=True)
    company_id         = ObjectIdField(required=True)
    role               = ReferenceField(Role, required=True)
    is_default_company = BooleanField(default=False)
    is_active          = BooleanField(default=True)

    meta = {'collection': 'company_user_mappings'}

class UserSession(Document):
    user       = ReferenceField(User, required=True)
    token      = StringField(required=True, unique=True)
    login_time = DateTimeField(default=datetime.utcnow)
    last_active = DateTimeField(default=datetime.utcnow)
    logout_time = DateTimeField()
    is_expired = BooleanField(default=False)

    meta = {'collection': 'user_sessions'}

    def touch(self):
        self.last_active = datetime.utcnow()
        self.save()

def seed_auth():
    # Create Super Admin if not exists
    admin = User.objects(username="admin").first()
    if not admin:
        admin = User(username="admin", is_super_admin=True)
        admin.set_password("admin123")
        admin.save()
        print("Super Admin created: admin / admin123")
    else:
        print("Super Admin already exists")

    # Create Default Roles
    roles = ["Company Admin", "Accountant", "Sales User", "Viewer"]
    for role_name in roles:
        Role.objects(name=role_name).update_one(set__name=role_name, upsert=True)
    
    print("Default roles seeded")

