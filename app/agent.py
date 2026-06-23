# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import google.auth

# Configure Vertex AI or AI Studio based on available credentials
if "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    try:
        _, project_id = google.auth.default()
        if project_id:
            os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    except Exception:
        pass

os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

DB_FILE = "expenses.json"


def _load_expenses() -> list:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _save_expenses(expenses: list):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(expenses, f, indent=2)
    except Exception:
        pass


def log_expense(
    amount: float, category: str, description: str, merchant: str, date: str = None
) -> dict:
    """Logs an expense transaction with validation checks for duplicates and budget limits.

    Args:
        amount: The expense amount in USD (e.g., 25.50).
        category: The expense category (e.g., "Meals", "Travel", "Software", "Office Supplies").
        description: A brief description of the expense.
        merchant: The name of the merchant/vendor.
        date: Optional date of the expense in YYYY-MM-DD format. If omitted, today's date is used.

    Returns:
        dict: A dictionary containing the logged expense details, status, and any warnings.
    """
    if not date:
        date = datetime.date.today().strftime("%Y-%m-%d")

    expenses = _load_expenses()

    # 1. Duplicate check (same amount, merchant, date, category)
    is_duplicate = False
    for exp in expenses:
        if (
            abs(exp["amount"] - amount) < 1e-9
            and exp["merchant"].lower() == merchant.lower()
            and exp["date"] == date
            and exp["category"].lower() == category.lower()
        ):
            is_duplicate = True
            break

    # 2. Safety limit check (limit >= $100 requires manager approval)
    status = "approved"
    warnings = []
    if amount >= 100.0:
        status = "pending_manager_approval"
        warnings.append("Expense exceeds $100 limit and requires manager approval.")

    if is_duplicate:
        warnings.append(
            "Potential duplicate expense detected with the same amount, merchant, date, and category."
        )

    new_expense = {
        "id": len(expenses) + 1,
        "amount": amount,
        "category": category,
        "description": description,
        "merchant": merchant,
        "date": date,
        "status": status,
    }

    expenses.append(new_expense)
    _save_expenses(expenses)

    return {"status": "success", "expense": new_expense, "warnings": warnings}


def list_expenses(
    category: str = None, min_amount: float = None, max_amount: float = None
) -> dict:
    """Lists logged expenses, with optional filters for category and amount.

    Args:
        category: Optional category filter (e.g., "Meals").
        min_amount: Optional minimum amount filter.
        max_amount: Optional maximum amount filter.

    Returns:
        dict: A dictionary containing the list of matching expenses.
    """
    expenses = _load_expenses()
    filtered = []
    for exp in expenses:
        if category and exp["category"].lower() != category.lower():
            continue
        if min_amount is not None and exp["amount"] < min_amount:
            continue
        if max_amount is not None and exp["amount"] > max_amount:
            continue
        filtered.append(exp)

    return {"status": "success", "count": len(filtered), "expenses": filtered}


def get_expense_summary() -> dict:
    """Provides a summary of expenses, including total spending and breakdown by category.

    Returns:
        dict: A dictionary containing overall spending and category-wise spending totals.
    """
    expenses = _load_expenses()
    total_spend = 0.0
    category_spend = {}

    for exp in expenses:
        amount = exp["amount"]
        total_spend += amount
        cat = exp["category"]
        category_spend[cat] = category_spend.get(cat, 0.0) + amount

    return {
        "status": "success",
        "total_spend": total_spend,
        "category_breakdown": category_spend,
        "total_count": len(expenses),
    }


root_agent = Agent(
    name="expense_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="You are an expert Expense Management Agent. You help users submit, list, and summarize their expense reports. Always use the provided tools to record and retrieve transactions. Validate every expense: if a transaction is $100 or more, warn the user that manager approval is required, and flag potential duplicates.",
    tools=[log_expense, list_expenses, get_expense_summary],
)

app = App(
    root_agent=root_agent,
    name="app",
)
