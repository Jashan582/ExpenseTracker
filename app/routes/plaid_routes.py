from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from plaid.exceptions import ApiException

from app import db
from app.models import PlaidItem, Account, Transaction, Category, CategoryRule
from app.crypto import encrypt_token, decrypt_token
from app.plaid_categories import label_for_pfc
from app.ai_categorize import ai_guess_category
from app.plaid_client import (
    create_link_token,
    exchange_public_token,
    get_accounts,
    sync_transactions,
)

plaid_bp = Blueprint("plaid", __name__)

# Colors cycled through for categories auto-created from Plaid's own
# taxonomy (e.g. "Food and Drink") — the user can change these anytime
# on the Categories page.
_AUTO_CATEGORY_PALETTE = [
    "#3C6E5D", "#C68B3D", "#5B7A99", "#8B5E83",
    "#A6483A", "#4E8B7D", "#9A9A92", "#14242C",
]


@plaid_bp.route("/create_link_token", methods=["POST"])
@login_required
def create_link_token_route():
    """Frontend calls this to get a link_token, then opens Plaid Link with it."""
    try:
        link_token = create_link_token(current_user.id)
        return jsonify({"link_token": link_token})
    except ApiException as e:
        return jsonify({"error": str(e)}), 400


@plaid_bp.route("/exchange_public_token", methods=["POST"])
@login_required
def exchange_public_token_route():
    """Frontend calls this once the user finishes linking a bank in Plaid Link."""
    public_token = request.json.get("public_token")
    if not public_token:
        return jsonify({"error": "public_token is required"}), 400

    try:
        access_token, item_id = exchange_public_token(public_token)
    except ApiException as e:
        return jsonify({"error": str(e)}), 400

    plaid_item = PlaidItem(
        user_id=current_user.id,
        item_id=item_id,
        access_token_encrypted=encrypt_token(access_token),
    )
    db.session.add(plaid_item)
    db.session.flush()

    # Pull in the accounts (cards) under this connection right away
    for acct in get_accounts(access_token):
        db.session.add(
            Account(
                plaid_item_id=plaid_item.id,
                plaid_account_id=acct.account_id,
                name=acct.name,
                official_name=acct.official_name,
                mask=acct.mask,
                type=str(acct.type),
                subtype=str(acct.subtype) if acct.subtype else None,
            )
        )
        if acct.official_name and "bank" in (acct.official_name or "").lower():
            plaid_item.institution_name = acct.official_name

    db.session.commit()

    # Kick off an initial transaction sync so the dashboard isn't empty
    _sync_item(plaid_item)

    return jsonify({"status": "linked", "item_id": item_id})


@plaid_bp.route("/sync", methods=["POST"])
@login_required
def sync_route():
    """Manual 'refresh' button — pulls new transactions for all of this user's items."""
    items = PlaidItem.query.filter_by(user_id=current_user.id).all()
    total_new = 0
    for item in items:
        total_new += _sync_item(item)
    return jsonify({"status": "ok", "new_transactions": total_new})


def _sync_item(plaid_item: PlaidItem) -> int:
    access_token = decrypt_token(plaid_item.access_token_encrypted)
    added, modified, removed, next_cursor = sync_transactions(
        access_token, plaid_item.transactions_cursor
    )

    tenant_id = plaid_item.user.tenant_id
    account_map = {a.plaid_account_id: a.id for a in plaid_item.accounts}
    rules = (
        CategoryRule.query.filter_by(user_id=plaid_item.user_id)
        .order_by(CategoryRule.priority.desc())
        .all()
    )
    uncategorized = Category.query.filter_by(
        tenant_id=tenant_id, name="Uncategorized"
    ).first()

    new_count = 0
    for txn in added:
        account_id = account_map.get(txn.account_id)
        if not account_id:
            continue

        merchant = txn.merchant_name or txn.name
        pfc_primary = (
            txn.personal_finance_category.primary
            if txn.personal_finance_category
            else None
        )
        category_id = _determine_category_id(
            merchant, rules, pfc_primary, tenant_id, uncategorized
        )

        db.session.add(
            Transaction(
                account_id=account_id,
                category_id=category_id,
                plaid_transaction_id=txn.transaction_id,
                merchant_name=txn.merchant_name,
                name=txn.name,
                amount=txn.amount,
                iso_currency_code=txn.iso_currency_code,
                date=txn.date,
                pending=txn.pending,
                plaid_category_primary=pfc_primary,
                account_owner=txn.account_owner,
            )
        )
        new_count += 1

    for txn in modified:
        existing = Transaction.query.filter_by(plaid_transaction_id=txn.transaction_id).first()
        if existing:
            existing.amount = txn.amount
            existing.pending = txn.pending

    for removed_txn in removed:
        Transaction.query.filter_by(
            plaid_transaction_id=removed_txn.transaction_id
        ).delete()

    plaid_item.transactions_cursor = next_cursor
    db.session.commit()
    return new_count


def _determine_category_id(merchant, rules, pfc_primary, tenant_id, uncategorized):
    """
    Categorization priority:
      1. A user-defined merchant-match rule (most specific — the user said so directly)
      2. Plaid's own Personal Finance Category (free, ~90%+ accurate)
      3. An AI guess against the tenant's existing categories (only when Plaid has nothing)
      4. Uncategorized, as a last resort
    """
    category_id = _match_category(merchant, rules)
    if category_id:
        return category_id

    pfc_label = label_for_pfc(pfc_primary)
    if pfc_label:
        return _get_or_create_category(tenant_id, pfc_label).id

    tenant_categories = Category.query.filter_by(tenant_id=tenant_id).all()
    category_names = [c.name for c in tenant_categories]
    ai_guess = ai_guess_category(merchant, category_names)
    if ai_guess:
        matched = next((c for c in tenant_categories if c.name == ai_guess), None)
        if matched:
            return matched.id

    return uncategorized.id if uncategorized else None


def _match_category(merchant_name: str, rules: list[CategoryRule]):
    if not merchant_name:
        return None
    lowered = merchant_name.lower()
    for rule in rules:
        if rule.match_text.lower() in lowered:
            return rule.category_id
    return None


def _color_for_name(name: str) -> str:
    idx = sum(ord(c) for c in name) % len(_AUTO_CATEGORY_PALETTE)
    return _AUTO_CATEGORY_PALETTE[idx]


def _get_or_create_category(tenant_id: int, name: str) -> Category:
    cat = Category.query.filter_by(tenant_id=tenant_id, name=name).first()
    if cat:
        return cat
    cat = Category(tenant_id=tenant_id, name=name, color=_color_for_name(name))
    db.session.add(cat)
    db.session.flush()
    return cat