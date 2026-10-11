from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user

from app import db
from app.models import Category, CategoryRule, Transaction

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/categories")
@login_required
def index():
    return render_template("categories.html")


@categories_bp.route("/api/categories", methods=["GET"])
@login_required
def list_categories():
    categories = (
        Category.query.filter_by(tenant_id=current_user.tenant_id)
        .order_by(Category.name)
        .all()
    )
    result = []
    for c in categories:
        rules = CategoryRule.query.filter_by(category_id=c.id, user_id=current_user.id).all()
        result.append(
            {
                "id": c.id,
                "name": c.name,
                "color": c.color,
                "is_default": c.is_default,
                "rules": [{"id": r.id, "match_text": r.match_text} for r in rules],
            }
        )
    return jsonify({"categories": result})


@categories_bp.route("/api/categories", methods=["POST"])
@login_required
def create_category():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    color = data.get("color") or "#6B7268"

    if not name:
        return jsonify({"error": "name is required"}), 400

    existing = Category.query.filter_by(tenant_id=current_user.tenant_id, name=name).first()
    if existing:
        return jsonify({"error": "a category with that name already exists"}), 400

    cat = Category(tenant_id=current_user.tenant_id, name=name, color=color)
    db.session.add(cat)
    db.session.commit()
    return jsonify({"id": cat.id, "name": cat.name, "color": cat.color})


@categories_bp.route("/api/categories/<int:cat_id>", methods=["PUT"])
@login_required
def update_category(cat_id):
    cat = Category.query.filter_by(id=cat_id, tenant_id=current_user.tenant_id).first()
    if not cat:
        return jsonify({"error": "not found"}), 404

    data = request.json or {}
    if data.get("name", "").strip():
        cat.name = data["name"].strip()
    if "color" in data:
        cat.color = data["color"]

    db.session.commit()
    return jsonify({"status": "ok"})


@categories_bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
@login_required
def delete_category(cat_id):
    cat = Category.query.filter_by(id=cat_id, tenant_id=current_user.tenant_id).first()
    if not cat:
        return jsonify({"error": "not found"}), 404
    if cat.name == "Uncategorized":
        return jsonify({"error": "can't delete the Uncategorized category"}), 400

    # Move any transactions in this category to Uncategorized rather than
    # leaving them orphaned or silently deleting spending history.
    uncategorized = Category.query.filter_by(
        tenant_id=current_user.tenant_id, name="Uncategorized"
    ).first()
    Transaction.query.filter_by(category_id=cat.id).update(
        {"category_id": uncategorized.id if uncategorized else None}
    )
    CategoryRule.query.filter_by(category_id=cat.id).delete()
    db.session.delete(cat)
    db.session.commit()
    return jsonify({"status": "ok"})


@categories_bp.route("/api/categories/<int:cat_id>/rules", methods=["POST"])
@login_required
def add_rule(cat_id):
    cat = Category.query.filter_by(id=cat_id, tenant_id=current_user.tenant_id).first()
    if not cat:
        return jsonify({"error": "not found"}), 404

    data = request.json or {}
    match_text = (data.get("match_text") or "").strip().lower()
    if not match_text:
        return jsonify({"error": "match_text is required"}), 400

    rule = CategoryRule(category_id=cat.id, user_id=current_user.id, match_text=match_text)
    db.session.add(rule)
    db.session.commit()
    return jsonify({"id": rule.id, "match_text": rule.match_text})


@categories_bp.route("/api/category_rules/<int:rule_id>", methods=["DELETE"])
@login_required
def delete_rule(rule_id):
    rule = CategoryRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if not rule:
        return jsonify({"error": "not found"}), 404

    db.session.delete(rule)
    db.session.commit()
    return jsonify({"status": "ok"})