from flask import Flask, g, jsonify, request
from backend.routes.company_routes import company_bp
from backend.routes.group_routes import group_bp
from backend.routes.ledger_routes import ledger_bp
from backend.routes.voucher_routes import voucher_bp
from backend.routes.report_routes import reports_bp
from backend.routes.inventory_routes import inventory_bp
from backend.routes.settings_routes import settings_bp
from backend.models.group import seed_default_groups
from backend.models.inventory import seed_defaults as seed_inventory
import os


def _request_company_id():
    if request.blueprint == "company" or request.path == "/api/health":
        return None
    cid = request.args.get("company_id")
    if cid:
        return cid
    data = request.get_json(silent=True) if request.is_json else None
    if isinstance(data, dict):
        return data.get("company_id")
    return None


def create_app():
    app = Flask(__name__)

    @app.before_request
    def use_company_database():
        company_id = _request_company_id()
        if not company_id:
            return None
        from backend.database import company_data_context
        try:
            g.company_db_context = company_data_context(company_id)
            g.company_db_context.__enter__()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.teardown_request
    def close_company_database(_exc):
        ctx = getattr(g, "company_db_context", None)
        if ctx:
            ctx.__exit__(None, None, None)

    app.register_blueprint(company_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(voucher_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(settings_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


def run_server():
    from dotenv import load_dotenv
    load_dotenv()
    seed_default_groups()
    seed_inventory()
    port = int(os.getenv("FLASK_PORT", 5050))
    app = create_app()
    app.run(port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_server()
