# ─────────────────────────────────────────────────────────────────────────────
#  Global application session — holds the active company context
# ─────────────────────────────────────────────────────────────────────────────
company_id:        str = ""
company_name:      str = ""
fiscal_year_from:  str = ""   # "YYYY-MM-DD"
fiscal_year_to:    str = ""   # "YYYY-MM-DD"
period_from:       str = ""   # "YYYY-MM-DD"
period_to:         str = ""   # "YYYY-MM-DD"


def set_company(cid: str, name: str, fy_from: str, fy_to: str) -> None:
    global company_id, company_name, fiscal_year_from, fiscal_year_to, period_from, period_to
    company_id       = cid
    company_name     = name
    fiscal_year_from = fy_from
    fiscal_year_to   = fy_to
    # Default period to full fiscal year
    period_from      = fy_from
    period_to        = fy_to


def clear():
    global company_id, company_name, fiscal_year_from, fiscal_year_to, period_from, period_to
    company_id = company_name = fiscal_year_from = fiscal_year_to = period_from = period_to = ""


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
