from mongoengine import Document, StringField, DateTimeField
from datetime import datetime

import backend.database  # ensure mongoengine.connect() is called


DEFAULT_GROUPS = [
    # Liabilities
    {"name": "Capital Account",              "nature": "Liability", "parent": None},
    {"name": "Reserves & Surplus",           "nature": "Liability", "parent": None},
    {"name": "Retained Earnings",            "nature": "Liability", "parent": None},
    {"name": "Loans (Liability)",            "nature": "Liability", "parent": None},
    {"name": "Secured Loans",                "nature": "Liability", "parent": "Loans (Liability)"},
    {"name": "Unsecured Loans",              "nature": "Liability", "parent": "Loans (Liability)"},
    {"name": "Current Liabilities",          "nature": "Liability", "parent": None},
    {"name": "Sundry Creditors",             "nature": "Liability", "parent": "Current Liabilities"},
    {"name": "Duties & Taxes",               "nature": "Liability", "parent": "Current Liabilities"},
    {"name": "Provisions",                   "nature": "Liability", "parent": "Current Liabilities"},
    {"name": "Suspense A/c",                 "nature": "Liability", "parent": None},
    # Assets
    {"name": "Fixed Assets",                 "nature": "Asset",     "parent": None},
    {"name": "Investments",                  "nature": "Asset",     "parent": None},
    {"name": "Loans & Advances (Asset)",     "nature": "Asset",     "parent": None},
    {"name": "Misc. Expenses (ASSET)",       "nature": "Asset",     "parent": None},
    {"name": "Deposits (Asset)",             "nature": "Asset",     "parent": None},
    {"name": "Current Assets",               "nature": "Asset",     "parent": None},
    {"name": "Cash-in-Hand",                 "nature": "Asset",     "parent": "Current Assets"},
    {"name": "Bank Accounts",                "nature": "Asset",     "parent": "Current Assets"},
    {"name": "Sundry Debtors",               "nature": "Asset",     "parent": "Current Assets"},
    {"name": "Stock-in-Hand",                "nature": "Asset",     "parent": "Current Assets"},
    # Income
    {"name": "Sales Accounts",               "nature": "Income",    "parent": None},
    {"name": "Direct Incomes",               "nature": "Income",    "parent": None},
    {"name": "Income (Direct)",              "nature": "Income",    "parent": None},
    {"name": "Indirect Incomes",             "nature": "Income",    "parent": None},
    {"name": "Income (Indirect)",            "nature": "Income",    "parent": None},
    # Expense
    {"name": "Purchase Accounts",            "nature": "Expense",   "parent": None},
    {"name": "Direct Expenses",              "nature": "Expense",   "parent": None},
    {"name": "Expenses (Direct)",            "nature": "Expense",   "parent": None},
    {"name": "Indirect Expenses",            "nature": "Expense",   "parent": None},
    {"name": "Expenses (Indirect)",          "nature": "Expense",   "parent": None},
]


class Group(Document):
    name       = StringField(required=True)
    nature     = StringField(required=True)
    parent     = StringField()
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'groups'}


# ── seed ───────────────────────────────────────────────────────────────────────
def seed_default_groups():
    if Group.objects.count() < len(DEFAULT_GROUPS):
        existing_names = {g.name for g in Group.objects.only('name')}
        for g in DEFAULT_GROUPS:
            if g["name"] not in existing_names:
                Group(name=g["name"], nature=g["nature"], parent=g.get("parent")).save()


# ── CRUD ───────────────────────────────────────────────────────────────────────
def get_all_groups() -> list:
    return [
        {"_id": str(g.id), "name": g.name, "nature": g.nature, "parent": g.parent or ""}
        for g in Group.objects.all()
    ]


def create_group(name: str, nature: str, parent: str = None) -> str:
    g = Group(name=name, nature=nature, parent=parent)
    g.save()
    return str(g.id)


def delete_group(group_id: str):
    Group.objects(id=group_id).delete()


def update_group(group_id: str, name: str, nature: str, parent: str = None):
    Group.objects(id=group_id).update_one(set__name=name, set__nature=nature,
                                          set__parent=parent)
