import requests
import os
from dotenv import load_dotenv

load_dotenv()
BASE_URL = f"http://127.0.0.1:{os.getenv('FLASK_PORT', 5050)}/api"


def _cid():
    """Return current company_id from session, or None."""
    try:
        from frontend import session
        return session.company_id or None
    except Exception:
        return None


def _company_params(path, params=None):
    params = dict(params or {})
    if path.startswith("/companies") or path == "/health" or "company_id" in params:
        return params or None
    c = _cid()
    if c:
        params["company_id"] = c
    return params or None


def _with_company_id(path, data=None):
    data = dict(data or {})
    if path.startswith("/companies") or "company_id" in data:
        return data
    c = _cid()
    if c:
        data["company_id"] = c
    return data


def _get(path, params=None):
    r = requests.get(BASE_URL + path, params=_company_params(path, params), timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path, data):
    r = requests.post(BASE_URL + path, params=_company_params(path), json=_with_company_id(path, data), timeout=10)
    r.raise_for_status()
    return r.json()


def _put(path, data):
    r = requests.put(BASE_URL + path, params=_company_params(path), json=_with_company_id(path, data), timeout=10)
    r.raise_for_status()
    return r.json()


def _delete(path):
    r = requests.delete(BASE_URL + path, params=_company_params(path), timeout=10)
    r.raise_for_status()
    return r.json()


# Companies
def list_companies():         return _get("/companies/")
def get_company(cid):         return _get(f"/companies/{cid}")
def create_company(data):     return _post("/companies/", data)
def update_company(cid, d):   return _put(f"/companies/{cid}", d)
def delete_company(cid):      return _delete(f"/companies/{cid}")

# Groups  (global — not company-scoped)
def list_groups():            return _get("/groups/")
def create_group(data):       return _post("/groups/", data)
def update_group(gid, d):     return _put(f"/groups/{gid}", d)

# Ledgers
def list_ledgers():
    p = {}
    c = _cid()
    if c: p["company_id"] = c
    return _get("/ledgers/", params=p)

def create_ledger(data):
    data["company_id"] = _cid()
    return _post("/ledgers/", data)

def get_ledger(lid):          return _get(f"/ledgers/{lid}")
def update_ledger(lid, d):    return _put(f"/ledgers/{lid}", d)
def delete_ledger(lid):       return _delete(f"/ledgers/{lid}")
def ledger_balance(lid):      return _get(f"/ledgers/{lid}/balance")

# Vouchers
def voucher_types():          return _get("/vouchers/types")

def list_vouchers(**kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get("/vouchers/", params=kw)

def get_voucher(vid):         return _get(f"/vouchers/{vid}")

def create_voucher(data):
    data["company_id"] = _cid()
    return _post("/vouchers/", data)

def delete_voucher(vid):      return _delete(f"/vouchers/{vid}")
def update_voucher(vid, data):return _put(f"/vouchers/{vid}", data)
def get_voucher_stock_txns(vid): return _get(f"/vouchers/{vid}/stock-txns")

def create_accounting_voucher(data):
    data["company_id"] = _cid()
    return _post("/vouchers/accounting", data)

def list_outstanding(ledger_id=None, vtype=None, include_vid=None):
    p = {"company_id": _cid()}
    if ledger_id: p["ledger_id"] = ledger_id
    if vtype: p["type"] = vtype
    if include_vid: p["include_vid"] = include_vid
    return _get("/vouchers/outstanding", params=p)

# Reports
def trial_balance(**kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get("/reports/trial-balance", params=kw)

def profit_loss(**kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get("/reports/profit-loss", params=kw)

def ledger_statement(lid, **kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get(f"/reports/ledger-statement/{lid}", params=kw)

def balance_sheet(**kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get("/reports/balance-sheet", params=kw)

# Inventory
def list_units():             return _get("/inventory/units")
def create_unit(data):        return _post("/inventory/units", data)
def list_stock_groups():      return _get("/inventory/stock-groups")
def create_stock_group(data): return _post("/inventory/stock-groups", data)

def list_stock_categories(**kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get("/inventory/stock-categories", params=kw)

def create_stock_category(data):
    data["company_id"] = _cid()
    return _post("/inventory/stock-categories", data)

def update_stock_category(cid, d): return _put(f"/inventory/stock-categories/{cid}", d)
def delete_stock_category(cid):    return _delete(f"/inventory/stock-categories/{cid}")

def list_stock_items():
    p = {}
    c = _cid()
    if c: p["company_id"] = c
    return _get("/inventory/items", params=p)

def get_stock_item(iid):      return _get(f"/inventory/items/{iid}")

def create_stock_item(data):
    data["company_id"] = _cid()
    return _post("/inventory/items", data)

def update_stock_item(iid, d):return _put(f"/inventory/items/{iid}", d)
def delete_stock_item(iid):   return _delete(f"/inventory/items/{iid}")

def stock_summary(**kw):
    c = _cid()
    if c: kw["company_id"] = c
    return _get("/inventory/stock-summary", params=kw)

