from backend.models.voucher import Voucher, VoucherItem, get_outstanding_vouchers
from bson import ObjectId

def debug():
    cid = str(Voucher.objects.all()[0].company_id)
    lid = "69e4a2759ae9d21170a9ff4e" # Sunny
    print(f"Company ID: {cid}")
    print(f"Ledger ID: {lid}")
    
    res = get_outstanding_vouchers(cid, lid)
    print(f"Found {len(res)} outstanding vouchers for lid {lid}")
    for v in res:
        print(f"- {v['voucher_no']} {v['voucher_type']} amt={v['amount']}")

if __name__ == "__main__":
    debug()
