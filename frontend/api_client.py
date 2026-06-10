import requests
import os
from dotenv import load_dotenv

load_dotenv()
BASE_URL = f"http://127.0.0.1:{os.getenv('FLASK_PORT', 5050)}/api"

def set_server_address(ip, port=None):
    global BASE_URL
    if port is None:
        port = os.getenv('FLASK_PORT', 5050)
    BASE_URL = f"http://{ip}:{port}/api"


def _cid():
    """Return current company_id from session, or None."""
    try:
        from frontend import session
        return session.get("company_id")
    except Exception:
        return None

def _token():
    """Return current session token."""
    try:
        from frontend import session
        return session.get("token")
    except Exception:
        return None


def _company_params(path, params=None):
    params = dict(params or {})
    if path.startswith("/company") or path.startswith("/auth") or path == "/health" or "company_id" in params:
        return params or None
    c = _cid()
    if c:
        params["company_id"] = c
    return params or None


def _with_company_id(path, data=None):
    data = dict(data or {})
    if path.startswith("/company") or path.startswith("/auth") or "company_id" in data:
        return data
    c = _cid()
    if c:
        data["company_id"] = c
    return data


def _headers():
    token = _token()
    if token:
        return {"Authorization": token}
    return {}


def _get(path, params=None):
    r = requests.get(BASE_URL + path, params=_company_params(path, params), headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path, data):
    r = requests.post(BASE_URL + path, params=_company_params(path), json=_with_company_id(path, data), headers=_headers(), timeout=10)
    if r.status_code >= 400:
        try:
            err = r.json().get("error", r.text)
            raise Exception(f"{r.status_code} Error: {err}")
        except:
            r.raise_for_status()
    return r.json()


def _put(path, data):
    r = requests.put(BASE_URL + path, params=_company_params(path), json=_with_company_id(path, data), headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def _delete(path):
    r = requests.delete(BASE_URL + path, params=_company_params(path), headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


# Auth
def login(username, password): 
    return _post("/auth/login", {"username": username, "password": password})
def validate_session():       
    return _post("/auth/validate_session", {})
def logout():                 
    return _post("/auth/logout", {})
def get_my_companies():       
    return _get("/auth/my_companies")
def get_permissions(cid=None): 
    return _get("/auth/permissions", params={"company_id": cid} if cid else {})

# Companies
def list_companies():         return _get("/company/")
def get_company(cid):         return _get(f"/company/{cid}")
def create_company(data):     return _post("/company/", data)
def update_company(cid, d):   return _put(f"/company/{cid}", d)
def delete_company(cid):      return _delete(f"/company/{cid}")

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


# Settings (Backup/Restore)
def list_users():
    return _get('/auth/users')

def create_user(data):
    return _post('/auth/users', data)

def list_roles():
    return _get('/auth/roles')

def list_all_companies():
    return _get('/auth/companies/all')

def create_mapping(data):
    return _post('/auth/mappings', data)
def list_mappings(company_id=None, user_id=None):
    p = {}
    if company_id: p['company_id'] = company_id
    if user_id: p['user_id'] = user_id
    return _get('/auth/mappings', params=p)

def delete_mapping(mid):
    return _delete(f'/auth/mappings/{mid}')

def backup_company(company_id):
    params = {"company_id": company_id}
    r = requests.get(BASE_URL + "/settings/backup", params=params, timeout=30)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Disposition", "")


def restore_company(company_id, file_path):
    params = {"company_id": company_id}
    with open(file_path, "rb") as f:
        files = {"file": f}
        r = requests.post(BASE_URL + "/settings/restore", params=params, files=files, timeout=30)
    r.raise_for_status()
    return r.json()

# GST Reports
def gstr1(from_date=None, to_date=None):
    p = {}
    if from_date: p["from"] = from_date
    if to_date: p["to"] = to_date
    c = _cid()
    if c: p["company_id"] = c
    return _get("/reports/gstr1", params=p)

def gstr3b(from_date=None, to_date=None):
    p = {}
    if from_date: p["from"] = from_date
    if to_date: p["to"] = to_date
    c = _cid()
    if c: p["company_id"] = c
    return _get("/reports/gstr3b", params=p)

def gst_summary(from_date=None, to_date=None):
    p = {}
    if from_date: p["from"] = from_date
    if to_date: p["to"] = to_date
    c = _cid()
    if c: p["company_id"] = c
    return _get("/reports/gst-summary", params=p)

def save_role_permissions(data):
    return _post('/auth/roles/permissions', data)

def get_role_permissions(role_id):
    return _get(f'/auth/roles/{role_id}/permissions')

