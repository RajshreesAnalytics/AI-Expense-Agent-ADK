import os

import pytest

from app.agent import DB_FILE, get_expense_summary, list_expenses, log_expense


@pytest.fixture(autouse=True)
def clean_db():
    # Remove database file if it exists before and after each test
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass
    yield
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass


def test_log_expense():
    res = log_expense(
        amount=50.00,
        category="Meals",
        description="Team lunch",
        merchant="Burger Place",
        date="2026-06-22",
    )
    assert res["status"] == "success"
    assert res["expense"]["amount"] == 50.00
    assert res["expense"]["status"] == "approved"
    assert len(res["warnings"]) == 0


def test_log_expense_large_amount():
    res = log_expense(
        amount=100.00,
        category="Travel",
        description="Flight tickets",
        merchant="Airline Inc.",
        date="2026-06-22",
    )
    assert res["status"] == "success"
    assert res["expense"]["status"] == "pending_manager_approval"
    assert any("exceeds $100 limit" in w for w in res["warnings"])


def test_log_expense_duplicate():
    log_expense(10.0, "Meals", "Coffee", "Coffee Shop", "2026-06-22")
    res = log_expense(10.0, "Meals", "Coffee", "Coffee Shop", "2026-06-22")
    assert res["status"] == "success"
    assert any("duplicate" in w.lower() for w in res["warnings"])


def test_list_expenses_and_summary():
    log_expense(20.0, "Meals", "Lunch", "Deli", "2026-06-22")
    log_expense(300.0, "Travel", "Hotel", "Inn", "2026-06-22")

    # Check listing
    list_res = list_expenses(category="Meals")
    assert list_res["count"] == 1
    assert list_res["expenses"][0]["amount"] == 20.0

    # Check summary
    summary_res = get_expense_summary()
    assert summary_res["total_spend"] == 320.0
    assert summary_res["category_breakdown"]["Meals"] == 20.0
    assert summary_res["category_breakdown"]["Travel"] == 300.0
