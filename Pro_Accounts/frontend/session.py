# ─────────────────────────────────────────────────────────────────────────────
#  Global application session — holds the active company context
# ─────────────────────────────────────────────────────────────────────────────
company_id:        str = ""
company_name:      str = ""
fiscal_year_from:  str = ""   # "YYYY-MM-DD"
fiscal_year_to:    str = ""   # "YYYY-MM-DD"


def set_company(cid: str, name: str, fy_from: str, fy_to: str) -> None:
    global company_id, company_name, fiscal_year_from, fiscal_year_to
    company_id       = cid
    company_name     = name
    fiscal_year_from = fy_from
    fiscal_year_to   = fy_to


def clear():
    global company_id, company_name, fiscal_year_from, fiscal_year_to
    company_id = company_name = fiscal_year_from = fiscal_year_to = ""
