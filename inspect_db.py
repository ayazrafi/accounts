from backend.models.group import get_all_groups
from backend.models.ledger import get_all_ledgers
from backend.models.company import get_all_companies

companies = get_all_companies()
cid = companies[0]["_id"]
groups = get_all_groups()
ledgers = get_all_ledgers(cid)

print("Cash/Bank Ledgers:")
for l in ledgers:
    g_name = next((g["name"] for g in groups if g["_id"] == l["group"]), "Unknown")
    if g_name in ["Cash-in-Hand", "Bank Accounts"]:
        print(f"ID: {l['_id']} | Name: {l['name']} | Group: {g_name}")

print("\nSundry Debtors/Creditors:")
for l in ledgers:
    g_name = next((g["name"] for g in groups if g["_id"] == l["group"]), "Unknown")
    if g_name in ["Sundry Debtors", "Sundry Creditors"]:
        print(f"ID: {l['_id']} | Name: {l['name']} | Group: {g_name}")
