#  Global application session — holds the active user and company context
# ─────────────────────────────────────────────────────────────────────────────
import os
import json

SESSION_FILE = ".session_data"

token:             str = ""
user_id:           str = ""
username:          str = ""
is_super_admin:    bool = False

company_id:        str = ""
company_name:      str = ""
fiscal_year_from:  str = ""   # "YYYY-MM-DD"
fiscal_year_to:    str = ""   # "YYYY-MM-DD"
period_from:       str = ""   # "YYYY-MM-DD"
period_to:         str = ""   # "YYYY-MM-DD"

permissions:       dict = {}

def set_user(u_id: str, u_name: str, u_token: str, super_admin: bool = False) -> None:
    global user_id, username, token, is_super_admin
    user_id = u_id
    username = u_name
    token = u_token
    is_super_admin = super_admin
    save()

def save():
    data = {
        "token": token,
        "user_id": user_id,
        "username": username,
        "is_super_admin": is_super_admin
    }
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def load():
    global user_id, username, token, is_super_admin
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            user_id = data.get("user_id", "")
            username = data.get("username", "")
            token = data.get("token", "")
            is_super_admin = data.get("is_super_admin", False)
            return bool(token)
    except:
        return False

def set_company(cid: str, name: str, fy_from: str, fy_to: str) -> None:
    global company_id, company_name, fiscal_year_from, fiscal_year_to, period_from, period_to
    company_id       = cid
    company_name     = name
    fiscal_year_from = fy_from
    fiscal_year_to   = fy_to
    # Default period to full fiscal year
    period_from      = fy_from
    period_to        = fy_to

def get(key):
    return globals().get(key)

def clear():
    global company_id, company_name, fiscal_year_from, fiscal_year_to, period_from, period_to, token, user_id, username, is_super_admin, permissions
    company_id = company_name = fiscal_year_from = fiscal_year_to = period_from = period_to = token = user_id = username = ""
    is_super_admin = False
    permissions = {}
    if os.path.exists(SESSION_FILE):
        try: os.remove(SESSION_FILE)
        except: pass

from datetime import datetime

def get_start_date():
    if not period_from: return datetime.now()
    return datetime.strptime(period_from, "%Y-%m-%d")

def get_end_date():
    if not period_to: return datetime.now()
    return datetime.strptime(period_to, "%Y-%m-%d")

def get_financial_year_str():
    if not fiscal_year_from or not fiscal_year_to:
        return "2025-2026"
    y1 = fiscal_year_from[:4]
    y2 = fiscal_year_to[:4]
    return f"{y1}-{y2}"

def is_date_in_period(date_val):
    """
    Check if a date (string 'YYYY-MM-DD' or QDate) is within the active transaction period.
    Returns (bool, error_message).
    """
    if not period_from or not period_to:
        return True, ""
    
    from PySide6.QtCore import QDate
    if isinstance(date_val, str):
        d = QDate.fromString(date_val, "yyyy-MM-dd")
    else:
        d = date_val
    
    start = QDate.fromString(period_from, "yyyy-MM-dd")
    end = QDate.fromString(period_to, "yyyy-MM-dd")
    
    if d < start or d > end:
        return False, f"Date {d.toString('dd-MM-yyyy')} is outside active period ({period_from} to {period_to})"
    return True, ""

def has_permission(module: str, action: str) -> bool:
    """
    Check if the current user has permission for a specific module and action.
    module: 'sales', 'purchase', 'debit note', 'credit note', 'payment', 'receipt', 'contra', 'journal', 'ledger', 'item'
    action: 'view', 'add', 'edit', 'delete' (which maps to update)
    """
    if is_super_admin:
        return True
    
    # normalize names
    module_key = module.lower().strip()
    action_key = action.lower().strip()
    
    # map action 'edit' to 'can_add', 'update' to 'can_edit'
    action_field = 'can_view'
    if action_key == 'edit' or action_key == 'add':
        action_field = 'can_add'
    elif action_key == 'update':
        action_field = 'can_edit'
    elif action_key == 'delete':
        action_field = 'can_delete'
        
    if isinstance(permissions, dict) and "permissions" in permissions:
        for p in permissions["permissions"]:
            if p.get("module", "").lower().strip() == module_key:
                return bool(p.get(action_field, False))
                
    return False
