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
    
    # Get ledgers
    ledgers = requests.get(f"{BASE_URL}/ledgers/", params={"company_id": cid}).json()
    if not ledgers:
        print("No ledgers")
        return
    
    print("Sample Ledger:", ledgers[0])
    
    # Get groups
    groups = requests.get(f"{BASE_URL}/groups/").json()
    group_map = {g["_id"]: g["name"] for g in groups}
    
    for l in ledgers:
        gid = l.get("group")
        gname = group_map.get(str(gid), "NOT FOUND")
        print(f"Ledger: {l['name']}, GroupID: {gid}, GroupName: {gname}")

if __name__ == "__main__":
    check()
