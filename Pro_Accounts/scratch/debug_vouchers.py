import requests
import os

BASE_URL = "http://127.0.0.1:5050/api"

def check():
    # Get companies
    cos = requests.get(f"{BASE_URL}/companies/").json()
    if not cos:
        print("No companies")
        return
    cid = cos[0]["_id"]
    
    # Get vouchers
    vouchers = requests.get(f"{BASE_URL}/vouchers/", params={"company_id": cid}).json()
    if not vouchers:
        print("No vouchers")
        return
    
    # Find a Payment or Receipt
    for v in vouchers:
        if v["voucher_type"] in ["Payment", "Receipt"]:
            print("Found Voucher:", v)
            print("Entries:", v.get("entries"))
            return

if __name__ == "__main__":
    check()
