"""Tests for the weekly financial digest."""
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from ..services.weekly_digest import (
    _monday_of_week,
    _sunday_of_week,
    _week_range,
    _previous_week_range,
    _parse_week_date,
    _heuristic_insights,
)

# ---------- Unit tests for helpers ----------

def test_monday_of_week():
    d = date(2024, 3, 15)
    assert _monday_of_week(d) == date(2024, 3, 11)


def test_sunday_of_week():
    d = date(2024, 3, 15)
    assert _sunday_of_week(d) == date(2024, 3, 17)


def test_week_range():
    start, end = _week_range(date(2024, 3, 15))
    assert start == date(2024, 3, 11)
    assert end == date(2024, 3, 17)


def test_previous_week_range():
    start, end = _previous_week_range(date(2024, 3, 15))
    assert start == date(2024, 3, 4)
    assert end == date(2024, 3, 10)


def test_parse_week_date():
    assert _parse_week_date("2024-03-15") == date(2024, 3, 15)


def test_parse_week_date_default():
    today = date.today()
    assert _parse_week_date(None) == today


# ---------- Unit tests for heuristic insights ----------

def test_heuristic_expenses_exceed_income():
    current = {"income": 100, "expenses": 150, "net": -50}
    previous = {"income": 0, "expenses": 0}
    insights = _heuristic_insights(current, previous, [])
    assert any("exceeded" in i.lower() for i in insights)


def test_heuristic_positive_net():
    current = {"income": 200, "expenses": 100, "net": 100}
    previous = {"income": 0, "expenses": 0}
    insights = _heuristic_insights(current, previous, [])
    assert any("positive" in i.lower() for i in insights)


def test_heuristic_high_increase():
    current = {"income": 100, "expenses": 500, "net": -400}
    previous = {"income": 100, "expenses": 300, "net": -200}
    categories = [{"category_name": "Food", "total": 200}]
    insights = _heuristic_insights(current, previous, categories)
    assert any("increased" in i.lower() for i in insights)


# ---------- Integration tests ----------

def test_digest_requires_auth(client):
    resp = client.get("/weekly-digest")
    assert resp.status_code == 401


def test_digest_returns_valid_structure(client, auth_headers):
    resp = client.get("/weekly-digest", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "week_range" in data
    assert "summary" in data
    assert "comparison" in data
    assert "category_breakdown" in data
    assert "daily_series" in data
    assert "insights" in data


def test_digest_with_custom_week(client, auth_headers):
    resp = client.get("/weekly-digest?week=2024-01-15", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["week_range"]["start"] == "2024-01-15"
