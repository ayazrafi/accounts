from backend.models.voucher import VoucherItem
from bson import ObjectId

def check_types():
    items = list(VoucherItem.objects.all()[:10])
    for it in items:
        lid = it.ledger_id
        print(f"Item: {it.ledger_name}, lid type: {type(lid)}, lid: {lid}")

if __name__ == "__main__":
    check_types()
