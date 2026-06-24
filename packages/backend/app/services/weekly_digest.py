"""Weekly financial digest service."""
import logging
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Optional

from flask import current_app
from sqlalchemy import func, extract

from ..extensions import db
from ..models import Expense, Category

logger = logging.getLogger("finmind.digest")

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _sunday_of_week(d: date) -> date:
    return _monday_of_week(d) + timedelta(days=6)


def _week_range(d: date) -> tuple[date, date]:
    mon = _monday_of_week(d)
    return mon, mon + timedelta(days=6)


def _previous_week_range(d: date) -> tuple[date, date]:
    return _week_range(d - timedelta(days=7))


def _parse_week_date(week_str: Optional[str]) -> date:
    if week_str:
        try:
            return datetime.strptime(week_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    return date.today()


def _query_totals(user_id: int, start: date, end: date) -> dict:
    rows = (
        db.session.query(
            Expense.expense_type,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("count"),
        )
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start,
            Expense.spent_at <= end,
        )
        .group_by(Expense.expense_type)
        .all()
    )
    income = Decimal("0.00")
    expenses = Decimal("0.00")
    tx_count = 0
    for row in rows:
        tx_count += row.count
        if row.expense_type == "INCOME":
            income = row.total
        else:
            expenses += row.total
    return {
        "income": float(income),
        "expenses": float(expenses),
        "net": float(income - expenses),
        "transaction_count": tx_count,
    }


def _category_breakdown(user_id: int, start: date, end: date) -> list[dict]:
    rows = (
        db.session.query(
            Expense.category_id,
            Category.name,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("count"),
        )
        .outerjoin(Category, Expense.category_id == Category.id)
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start,
            Expense.spent_at <= end,
            Expense.expense_type == "EXPENSE",
        )
        .group_by(Expense.category_id, Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )
    return [
        {"category_id": r.category_id, "category_name": r.name or "Uncategorized",
         "total": float(r.total), "transaction_count": r.count}
        for r in rows
    ]


def _daily_series(user_id: int, start: date, end: date) -> list[dict]:
    rows = (
        db.session.query(
            Expense.spent_at,
            Expense.expense_type,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
        )
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start,
            Expense.spent_at <= end,
        )
        .group_by(Expense.spent_at, Expense.expense_type)
        .order_by(Expense.spent_at)
        .all()
    )
    daily = {}
    for r in rows:
        day = r.spent_at.isoformat() if hasattr(r.spent_at, "isoformat") else str(r.spent_at)
        if day not in daily:
            daily[day] = {"date": day, "income": 0.0, "expenses": 0.0}
        if r.expense_type == "INCOME":
            daily[day]["income"] += float(r.total)
        else:
            daily[day]["expenses"] += float(r.total)
    current = start
    result = []
    while current <= end:
        day_str = current.isoformat()
        result.append(daily.get(day_str, {"date": day_str, "income": 0.0, "expenses": 0.0}))
        current += timedelta(days=1)
    return result


def _heuristic_insights(current: dict, previous: dict, categories: list[dict]) -> list[str]:
    insights = []
    if current["expenses"] > current["income"]:
        insights.append("Your expenses exceeded your income this week. Consider reviewing discretionary spending.")
    if current["net"] > 0:
        insights.append(f"Positive net flow of ${current['net']:.2f}. Keep it up!")
    if previous["expenses"] > 0:
        pct = ((current["expenses"] - previous["expenses"]) / previous["expenses"]) * 100
        if pct > 20:
            insights.append(f"Expenses increased {pct:.0f}% compared to last week. Watch for spending trends.")
        elif pct < -20:
            insights.append(f"Expenses decreased {pct:.0f}% compared to last week. Great progress!")
    if categories:
        top = categories[0]
        insights.append(f"Top spending category: {top['category_name']} (${top['total']:.2f}).")
    return insights


def generate_digest(user_id: int, week_date: Optional[str] = None,
                    gemini_api_key: Optional[str] = None) -> dict:
    base_date = _parse_week_date(week_date)
    start, end = _week_range(base_date)
    prev_start, prev_end = _previous_week_range(base_date)

    current = _query_totals(user_id, start, end)
    previous = _query_totals(user_id, prev_start, prev_end)
    categories = _category_breakdown(user_id, start, end)
    daily = _daily_series(user_id, start, end)
    heuristic = _heuristic_insights(current, previous, categories)

    ai_summary = None
    if gemini_api_key or current_app.config.get("GEMINI_API_KEY"):
        try:
            from ..services.ai import monthly_budget_suggestion
            suggestion = monthly_budget_suggestion(
                user_id, start.strftime("%Y-%m"),
                gemini_api_key=gemini_api_key,
                persona="financial_summary"
            )
            ai_summary = suggestion.get("suggestion", str(suggestion))
        except Exception as e:
            logger.warning("AI summary failed: %s", e)
            ai_summary = "AI summary unavailable."

    return {
        "week_range": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": current,
        "comparison": {
            "previous_week": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
            "totals": previous,
            "changes": {
                "income_pct": _safe_pct(current["income"], previous["income"]),
                "expenses_pct": _safe_pct(current["expenses"], previous["expenses"]),
                "net_pct": _safe_pct(current["net"], previous["net"]),
            },
        },
        "category_breakdown": categories,
        "daily_series": daily,
        "insights": heuristic,
        "ai_summary": ai_summary,
    }


def _safe_pct(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 2)
