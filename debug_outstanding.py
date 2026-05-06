from backend.models.voucher import Voucher, VoucherItem
from bson import ObjectId

def debug():
    cid = list(Voucher.objects.all())[0].company_id
    print(f"Company ID: {cid}")
    vouchers = Voucher.objects(company_id=cid, outstanding_amount__gt=0.01)
    print(f"Found {vouchers.count()} vouchers with outstanding > 0")
    for v in vouchers:
        print(f"- {v.voucher_no} ({v.voucher_type}) amt={v.outstanding_amount}")
        items = VoucherItem.objects(voucher_id=v.id)
        for it in items:
            print(f"  * Item: {it.ledger_name} (ID: {it.ledger_id})")

if __name__ == "__main__":
    debug()
