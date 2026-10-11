from datetime import date
from calendar import month_name
from collections import defaultdict

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import extract

from app import db
from app.models import Transaction, Account, PlaidItem, Category

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    return render_template("dashboard.html")


@dashboard_bp.route("/api/account_owners")
@login_required
def list_account_owners():
    """
    Distinct account_owner values seen across this user's transactions, for
    populating the filter dropdown. Most institutions never populate this
    field, so "Unknown" is almost always one of the options.
    """
    rows = (
        db.session.query(Transaction.account_owner)
        .join(Account, Account.id == Transaction.account_id)
        .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
        .filter(PlaidItem.user_id == current_user.id)
        .distinct()
        .all()
    )
    named_owners = sorted({r[0] for r in rows if r[0]})
    has_unknown = any(r[0] is None for r in rows)

    owners = [{"value": name, "label": name} for name in named_owners]
    if has_unknown:
        owners.append({"value": "__unknown__", "label": "Unknown"})

    return jsonify({"owners": owners})


@dashboard_bp.route("/api/monthly_breakdown")
@login_required
def monthly_breakdown():
    """
    Returns per-category totals for a given month, shaped for a bar chart:
    { "month": "August 2026", "categories": [...], "totals": [...], "tips": [...] }

    Pass ?owner=<name> to scope to one account holder, or ?owner=__unknown__
    for transactions where no cardholder name was reported.
    """
    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    owner = request.args.get("owner")

    query = (
        db.session.query(
            Category.id, Category.name, Category.color, db.func.sum(Transaction.amount)
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .join(Account, Account.id == Transaction.account_id)
        .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
        .filter(
            PlaidItem.user_id == current_user.id,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
            Transaction.amount > 0,  # positive = money out, per Plaid's sign convention
        )
    )
    query = _apply_owner_filter(query, owner)

    rows = query.group_by(Category.id).order_by(db.func.sum(Transaction.amount).desc()).all()

    category_ids = [r[0] for r in rows]
    categories = [r[1] for r in rows]
    colors = [r[2] for r in rows]
    totals = [float(r[3]) for r in rows]

    tips = _generate_rule_based_tips(year, month, categories, totals, owner)

    count_query = (
        db.session.query(db.func.count(Transaction.id))
        .join(Account, Account.id == Transaction.account_id)
        .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
        .filter(
            PlaidItem.user_id == current_user.id,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
            Transaction.amount > 0,
        )
    )
    transaction_count = _apply_owner_filter(count_query, owner).scalar() or 0

    return jsonify(
        {
            "month": f"{month_name[month]} {year}",
            "category_ids": category_ids,
            "categories": categories,
            "colors": colors,
            "totals": totals,
            "tips": tips,
            "transaction_count": transaction_count,
        }
    )


@dashboard_bp.route("/api/spending_trend")
@login_required
def spending_trend():
    """
    Total spend per month for the trailing N months (default 6, including
    the current month), oldest first — shaped for a line/area chart.
    """
    months_back = int(request.args.get("months", 6))
    owner = request.args.get("owner")

    today = date.today()
    points = []
    year, month = today.year, today.month
    for _ in range(months_back):
        query = (
            db.session.query(db.func.sum(Transaction.amount))
            .join(Account, Account.id == Transaction.account_id)
            .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
            .filter(
                PlaidItem.user_id == current_user.id,
                extract("year", Transaction.date) == year,
                extract("month", Transaction.date) == month,
                Transaction.amount > 0,
            )
        )
        query = _apply_owner_filter(query, owner)
        total = float(query.scalar() or 0)
        points.append({"label": f"{month_name[month][:3]} {year}", "total": total})

        year, month = (year - 1, 12) if month == 1 else (year, month - 1)

    points.reverse()
    return jsonify({"points": points})


def _apply_owner_filter(query, owner: str | None):
    if owner == "__unknown__":
        return query.filter(Transaction.account_owner.is_(None))
    if owner:
        return query.filter(Transaction.account_owner == owner)
    return query


def _previous_month_totals(year: int, month: int, owner: str | None = None):
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    query = (
        db.session.query(Category.name, db.func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .join(Account, Account.id == Transaction.account_id)
        .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
        .filter(
            PlaidItem.user_id == current_user.id,
            extract("year", Transaction.date) == prev_year,
            extract("month", Transaction.date) == prev_month,
            Transaction.amount > 0,
        )
    )
    query = _apply_owner_filter(query, owner)
    rows = query.group_by(Category.id).all()
    return {name: float(total) for name, total in rows}


def _generate_rule_based_tips(year, month, categories, totals, owner=None):
    """
    Deterministic, no-API-call tips based on month-over-month change per
    category. This is the fast/free tier — an AI-generated layer can sit
    on top of this later using the same numbers as its prompt input.
    """
    tips = []
    prev_totals = _previous_month_totals(year, month, owner)
    current_by_cat = dict(zip(categories, totals))

    for name, amount in current_by_cat.items():
        prev = prev_totals.get(name)
        if prev and prev > 0:
            change_pct = ((amount - prev) / prev) * 100
            if change_pct >= 25:
                tips.append(
                    f"{name} spending is up {change_pct:.0f}% from last month "
                    f"(${prev:.0f} → ${amount:.0f})."
                )
            elif change_pct <= -25:
                tips.append(
                    f"Nice — {name} spending dropped {abs(change_pct):.0f}% "
                    f"from last month."
                )

    if current_by_cat:
        top_category = max(current_by_cat, key=current_by_cat.get)
        total_spend = sum(current_by_cat.values())
        top_share = (current_by_cat[top_category] / total_spend) * 100 if total_spend else 0
        if top_share >= 40:
            tips.append(
                f"{top_category} makes up {top_share:.0f}% of this month's spending — "
                f"your single biggest category."
            )

    if not tips:
        tips.append("Nothing unusual this month — spending looks steady across categories.")

    return tips