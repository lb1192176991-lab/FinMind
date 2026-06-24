"""Register all API route blueprints."""
from flask import Flask


def register_routes(app: Flask) -> None:
    from . import auth, bills, categories, dashboard, expenses, insights, reminders, digest, docs

    app.register_blueprint(auth.bp, url_prefix="/api/auth")
    app.register_blueprint(bills.bp, url_prefix="/api/bills")
    app.register_blueprint(categories.bp, url_prefix="/api/categories")
    app.register_blueprint(dashboard.bp, url_prefix="/api/dashboard")
    app.register_blueprint(expenses.bp, url_prefix="/api/expenses")
    app.register_blueprint(insights.bp, url_prefix="/api/insights")
    app.register_blueprint(reminders.bp, url_prefix="/api/reminders")
    app.register_blueprint(digest.bp, url_prefix="/api/digest")
    app.register_blueprint(docs.bp, url_prefix="/api/docs")
