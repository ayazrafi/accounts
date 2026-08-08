import os
from contextlib import ExitStack, contextmanager
from backend.config import load_env
import mongoengine
from bson import ObjectId

load_env()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = os.getenv("DB_NAME", "pro_accounts")

mongoengine.connect(db=DB_NAME, host=MONGO_URI)


def company_db_name(company_id: str) -> str:
    """Return the physical MongoDB database name for one company's data."""
    from backend.models.company import Company
    try:
        c = Company.objects(id=company_id).first()
        if c and getattr(c, "db_name", None):
            return c.db_name
    except Exception as e:
        print(f"Error fetching company DB name: {e}")
    return f"{DB_NAME}_company_{str(company_id).lower()}"


def _copy_collection(source_db, target_db, collection: str, match: dict | None = None) -> None:
    docs = list(source_db[collection].find(match or {}))
    if not docs:
        return
    for doc in docs:
        target_db[collection].replace_one({"_id": doc["_id"]}, doc, upsert=True)


def ensure_company_database(company_id: str) -> str:
    """
    Create/seed the company database and migrate existing single-DB data once.

    The main DB keeps the companies catalog. Accounting, inventory, and report data
    are stored in one database per company.
    """
    if not ObjectId.is_valid(company_id):
        raise ValueError("Invalid company_id")

    client = mongoengine.connection.get_connection()
    source_db = client[DB_NAME]
    target_name = company_db_name(company_id)
    target_db = client[target_name]
    if target_name not in mongoengine.connection._connection_settings:
        mongoengine.register_connection(alias=target_name, db=target_name, host=MONGO_URI)
    cid = ObjectId(company_id)

    shared_collections = ["groups", "stock_units", "stock_groups"]
    company_collections = [
        "ledgers",
        "vouchers",
        "voucher_items",
        "bill_wise_detail",
        "stock_categories",
        "stock_items",
        "stock_transactions",
        "signatures",
        "transports",
    ]


    meta = target_db["database_meta"]
    if not meta.find_one({"_id": "single_db_migration"}):
        for collection in shared_collections:
            if target_db[collection].count_documents({}) == 0:
                _copy_collection(source_db, target_db, collection)

        for collection in company_collections:
            _copy_collection(source_db, target_db, collection, {"company_id": cid})

        meta.update_one(
            {"_id": "single_db_migration"},
            {"$set": {"company_id": cid, "source_db": DB_NAME}},
            upsert=True,
        )

    return target_name


@contextmanager
def company_data_context(company_id: str):
    """
    Temporarily route company-owned documents to this company's database.

    Keep Company on the default DB so the company selector/catalog always stays
    in one place.
    """
    db_name = ensure_company_database(company_id)

    from mongoengine.context_managers import switch_db
    from backend.models.group import Group, seed_default_groups
    from backend.models.inventory import (
        StockUnit, StockGroup, StockCategory, StockItem, StockTransaction,
        seed_defaults as seed_inventory,
    )
    from backend.models.ledger import Ledger
    from backend.models.voucher import Voucher, VoucherItem, BillWiseDetail
    from backend.models.signature import Signature
    from backend.models.transport import Transport

    docs = [
        Group,
        StockUnit,
        StockGroup,
        StockCategory,
        StockItem,
        StockTransaction,
        Ledger,
        Voucher,
        VoucherItem,
        BillWiseDetail,
        Signature,
        Transport,
    ]


    with ExitStack() as stack:
        for doc in docs:
            stack.enter_context(switch_db(doc, db_name))
        seed_default_groups()
        seed_inventory()
        yield
