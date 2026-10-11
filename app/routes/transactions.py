from datetime import date

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import extract

from app import db
from app.models import Transaction, Account, PlaidItem, Category, CategoryRule

transactions_bp = Blueprint("transactions", __name__)


@transactions_bp.route("/transactions")
@login_required
def index():
    return render_template("transactions.html")


@transactions_bp.route("/api/transactions")
@login_required
def list_transactions():
    """
    Pass ?owner=<name> (or ?owner=__unknown__) and/or ?category_id=<id> to
    narrow the list. Both are optional and combine with AND when both given.
    """
    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    owner = request.args.get("owner")
    category_id = request.args.get("category_id", type=int)

    query = (
        db.session.query(Transaction, Category)
        .join(Account, Account.id == Transaction.account_id)
        .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .filter(
            PlaidItem.user_id == current_user.id,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
    )

    if owner == "__unknown__":
        query = query.filter(Transaction.account_owner.is_(None))
    elif owner:
        query = query.filter(Transaction.account_owner == owner)

    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    rows = query.order_by(Transaction.date.desc()).all()

    categories = (
        Category.query.filter_by(tenant_id=current_user.tenant_id)
        .order_by(Category.name)
        .all()
    )

    transactions = [
        {
            "id": txn.id,
            "date": txn.date.isoformat(),
            "merchant": txn.merchant_name or txn.name,
            "amount": float(txn.amount),
            "pending": txn.pending,
            "category_id": txn.category_id,
            # Only populated for institutions that report which sub-account/
            # cardholder made the charge — most don't, so this is often null.
            "account_owner": txn.account_owner,
        }
        for txn, cat in rows
    ]

    return jsonify(
        {
            "transactions": transactions,
            "categories": [{"id": c.id, "name": c.name, "color": c.color} for c in categories],
        }
    )


@transactions_bp.route("/api/transactions/<int:txn_id>/category", methods=["POST"])
@login_required
def update_transaction_category(txn_id):
    data = request.json or {}
    category_id = data.get("category_id")
    create_rule = bool(data.get("create_rule"))

    # Scope the lookup through the user's own accounts so one user can't
    # edit another tenant's transaction by guessing an id.
    txn = (
        db.session.query(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .join(PlaidItem, PlaidItem.id == Account.plaid_item_id)
        .filter(Transaction.id == txn_id, PlaidItem.user_id == current_user.id)
        .first()
    )
    if not txn:
        return jsonify({"error": "not found"}), 404

    txn.category_id = category_id

    if create_rule and category_id:
        merchant = (txn.merchant_name or txn.name or "").strip().lower()
        if merchant:
            existing = CategoryRule.query.filter_by(
                user_id=current_user.id, match_text=merchant
            ).first()
            if not existing:
                db.session.add(
                    CategoryRule(
                        category_id=category_id,
                        user_id=current_user.id,
                        match_text=merchant,
                    )
                )

    db.session.commit()
    return jsonify({"status": "ok"})