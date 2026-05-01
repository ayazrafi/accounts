from backend.models.voucher import ReceiptSalesVoucher

def count_records():
    count = ReceiptSalesVoucher.objects.count()
    print(f"Total ReceiptSalesVoucher records: {count}")
    for r in ReceiptSalesVoucher.objects.all():
        print(f"- Receipt: {r.voucher_id}, Sales: {r.ref_voucher_id}, Amt: {r.amount}")

if __name__ == "__main__":
    count_records()
