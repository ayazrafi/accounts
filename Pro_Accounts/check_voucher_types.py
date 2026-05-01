from backend.models.voucher import Voucher

def check_types():
    types = Voucher.objects.distinct("voucher_type")
    print(f"Voucher Types: {types}")

if __name__ == "__main__":
    check_types()
