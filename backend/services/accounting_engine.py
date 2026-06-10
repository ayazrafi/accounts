from bson import ObjectId
from backend.models.ledger import get_ledger_by_id
from backend.models.group import Group
from backend.models.voucher import Voucher, create_voucher

class AccountingEngine:
    def __init__(self, company_id: str):
        self.company_id = company_id
        self._group_cache = {}

    def _get_group_name(self, group_id: ObjectId) -> str:
        gid_str = str(group_id)
        if gid_str in self._group_cache:
            return self._group_cache[gid_str]
        
        group = Group.objects(id=group_id).first()
        name = group.name if group else ""
        self._group_cache[gid_str] = name
        return name

    def process_transaction(self, data: dict):
        """
        Processes a Payment or Receipt transaction.
        Returns a result dict with validation status and journal entry details.
        """
        entries = data.get("entries", [])
        if not entries:
            return self._error("No entries provided")

        dr_total = sum(float(e["amount"]) for e in entries if e["dr_cr"] == "Dr")
        cr_total = sum(float(e["amount"]) for e in entries if e["dr_cr"] == "Cr")

        if abs(dr_total - cr_total) > 0.01:
            return self._error(f"Total Debit ({dr_total}) must equal Total Credit ({cr_total})")

        # Core Rule: Only ONE Cash/Bank ledger allowed
        cash_bank_entries = []
        other_entries = []

        for e in entries:
            ledger = get_ledger_by_id(e["ledger_id"])
            if not ledger:
                return self._error(f"Ledger {e['ledger_id']} does not exist")
            
            group_name = self._get_group_name(ObjectId(ledger["group"]))
            e["group_name"] = group_name
            e["ledger_name"] = ledger["name"]

            if group_name in ["Cash-in-Hand", "Bank Accounts"]:
                cash_bank_entries.append(e)
            else:
                other_entries.append(e)

            # Block Sales/Purchase ledgers outright — they must never appear in Payment/Receipt.
            # 'Duties & Taxes' is intentionally NOT blocked here (e.g. GST Deposit payments are valid).
            if group_name in ["Sales Accounts", "Purchase Accounts"]:
                return self._error(f"Sales/Purchase ledger '{ledger['name']}' not allowed in payment/receipt. Use a Purchase/Sales voucher instead.")

        if len(cash_bank_entries) != 1:
            return self._error("Only ONE Cash/Bank ledger allowed per voucher")

        cb_entry = cash_bank_entries[0]
        v_type = "Receipt" if cb_entry["dr_cr"] == "Dr" else "Payment"

        # Scenario Validation — block only clearly wrong groups.
        # Payment/Receipt should NOT include Sales or Purchase ledgers.
        # Note: 'Duties & Taxes' IS allowed — paying GST to the govt (GST Deposit) is valid.
        invalid_for_payment = ["Sales Accounts", "Purchase Accounts"]
        for e in other_entries:
            gn = e["group_name"]
            if gn in invalid_for_payment:
                return self._error(
                    f"'{e['ledger_name']}' (under '{gn}') cannot be used in a Payment/Receipt voucher. "
                    "Use a Purchase or Journal voucher instead."
                )

        # Linking Validation (If Provided)
        linking = data.get("linking")
        if linking:
            ref_type = linking.get("reference_type", "OnAccount")
            refs = linking.get("references", [])
            total_ref_amount = sum(float(r["amount"]) for r in refs)

            if total_ref_amount > (dr_total if v_type == "Receipt" else cr_total):
                return self._error("Total reference amount exceeds voucher amount")

            for ref in refs:
                if ref.get("reference_type") == "On Account":
                    continue
                
                ref_voucher = Voucher.objects(id=ObjectId(ref["voucher_id"])).first()
                if not ref_voucher:
                    return self._error(f"Referenced voucher {ref['voucher_id']} does not exist")
                
                # Ledger must match check: 
                # (Ideally verify the party ledger on ref_voucher matches the party ledger in this transaction)

        # Success!
        return {
            "status": "Valid",
            "transaction_type": v_type,
            "journal_entry": {
                "dr": [e for e in entries if e["dr_cr"] == "Dr"],
                "cr": [e for e in entries if e["dr_cr"] == "Cr"]
            },
            "linking_summary": linking if linking else {"reference_type": "OnAccount", "references": []},
            "error": None
        }

    def _error(self, msg: str):
        return {
            "status": "Error",
            "error": msg,
            "transaction_type": None,
            "journal_entry": None,
            "linking_summary": None
        }
