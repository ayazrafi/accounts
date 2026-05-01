import sys
import os
from bson import ObjectId

# Mocking the database models for testing the engine logic
class MockGroup:
    def __init__(self, name):
        self.name = name

class MockLedger:
    @staticmethod
    def get_by_id(ledger_id):
        ledgers = {
            "bank_id": {"name": "Bank A/c", "group": "bank_group_id"},
            "cust_id": {"name": "Customer A/c", "group": "debtor_group_id"},
            "cash_id": {"name": "Cash A/c", "group": "cash_group_id"},
            "supp_id": {"name": "Supplier A/c", "group": "creditor_group_id"},
            "elec_id": {"name": "Electricity Exp", "group": "exp_group_id"},
            "gst_id":  {"name": "GST Ledger", "group": "gst_group_id"}
        }
        return ledgers.get(ledger_id)

class MockEngine:
    def __init__(self):
        self.groups = {
            "bank_group_id": "Bank Accounts",
            "debtor_group_id": "Sundry Debtors",
            "cash_group_id": "Cash-in-Hand",
            "creditor_group_id": "Sundry Creditors",
            "exp_group_id": "Indirect Expenses",
            "gst_group_id": "Duties & Taxes"
        }

    def _get_group_name(self, group_id):
        return self.groups.get(str(group_id), "Unknown")

    def process(self, data):
        # Using the logic from backend/services/accounting_engine.py
        entries = data.get("entries", [])
        dr_total = sum(e["amount"] for e in entries if e["dr_cr"] == "Dr")
        cr_total = sum(e["amount"] for e in entries if e["dr_cr"] == "Cr")

        if abs(dr_total - cr_total) > 0.01:
            return {"status": "Error", "error": "Total Debit must equal Total Credit"}

        cash_bank_entries = []
        other_entries = []
        for e in entries:
            ledger = MockLedger.get_by_id(e["ledger_id"])
            group_name = self._get_group_name(ledger["group"])
            e["group_name"] = group_name
            e["ledger_name"] = ledger["name"]
            if group_name in ["Cash-in-Hand", "Bank Accounts"]:
                cash_bank_entries.append(e)
            else:
                other_entries.append(e)
            
            if group_name in ["Duties & Taxes", "Sales Accounts", "Purchase Accounts"]:
                return {"status": "Error", "error": f"GST/Sales/Purchase ledger '{ledger['name']}' not allowed"}

        if len(cash_bank_entries) != 1:
            return {"status": "Error", "error": "Only ONE Cash/Bank ledger allowed"}

        cb_entry = cash_bank_entries[0]
        v_type = "Receipt" if cb_entry["dr_cr"] == "Dr" else "Payment"

        for e in other_entries:
            gn = e["group_name"]
            if v_type == "Receipt" and gn != "Sundry Debtors":
                return {"status": "Error", "error": "Receipt must be from Sundry Debtors"}
            if v_type == "Payment" and gn not in ["Sundry Creditors", "Indirect Expenses", "Direct Expenses"]:
                return {"status": "Error", "error": "Payment must be to Sundry Creditors or Expense"}

        return {
            "journal_entry": [f"{e['ledger_name']} {'Dr' if e['dr_cr'] == 'Dr' else 'Cr'} {e['amount']}" for e in entries],
            "transaction_type": v_type,
            "linking_summary": data.get("linking", {}).get("references", []),
            "status": "Valid"
        }

engine = MockEngine()

print("--- Test 1: Customer Payment Receive ---")
print(engine.process({
    "entries": [
        {"ledger_id": "bank_id", "amount": 3000, "dr_cr": "Dr"},
        {"ledger_id": "cust_id", "amount": 3000, "dr_cr": "Cr"}
    ]
}))

print("\n--- Test 2: Supplier Payment ---")
print(engine.process({
    "entries": [
        {"ledger_id": "supp_id", "amount": 5000, "dr_cr": "Dr"},
        {"ledger_id": "cash_id", "amount": 5000, "dr_cr": "Cr"}
    ]
}))

print("\n--- Test 3: Expense Payment ---")
print(engine.process({
    "entries": [
        {"ledger_id": "elec_id", "amount": 2000, "dr_cr": "Dr"},
        {"ledger_id": "bank_id", "amount": 2000, "dr_cr": "Cr"}
    ]
}))

print("\n--- Test 4: Invalid (GST Ledger) ---")
print(engine.process({
    "entries": [
        {"ledger_id": "gst_id", "amount": 500, "dr_cr": "Dr"},
        {"ledger_id": "cash_id", "amount": 500, "dr_cr": "Cr"}
    ]
}))
