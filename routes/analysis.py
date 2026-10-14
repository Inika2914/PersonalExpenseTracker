import io
import csv
from datetime import datetime
from collections import defaultdict

from flask import Blueprint, render_template, redirect, url_for, request, flash, Response
from flask_login import login_required, current_user

from models import db
from models.transaction import Transaction
from models.category import Category
from models.budget import Budget

analysis_bp = Blueprint("analysis", __name__)


def _current_month_transactions(user_id):
    now = datetime.utcnow()
    return [t for t in Transaction.query.filter_by(user_id=user_id).all()
            if t.date.year == now.year and t.date.month == now.month]


@analysis_bp.route("/dashboard")
@login_required
def dashboard():
    all_txns = Transaction.query.filter_by(user_id=current_user.id).all()
    total_income = sum(t.amount for t in all_txns if t.type == "income")
    total_expense = sum(t.amount for t in all_txns if t.type == "expense")
    balance = total_income - total_expense

    recent = sorted(all_txns, key=lambda t: t.date, reverse=True)[:5]

    return render_template(
        "dashboard.html",
        user=current_user,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        recent=recent,
        txn_count=len(all_txns),
    )


@analysis_bp.route("/analysis/charts")
@login_required
def charts():
    txns = Transaction.query.filter_by(user_id=current_user.id, type="expense").all()

    # Category breakdown (for a pie/bar chart)
    category_totals = defaultdict(float)
    for t in txns:
        name = t.category.name if t.category else "Uncategorized"
        category_totals[name] += t.amount

    # Monthly trend (for a line chart) - last 6 months of expense totals
    monthly_totals = defaultdict(float)
    for t in txns:
        key = t.date.strftime("%Y-%m")
        monthly_totals[key] += t.amount
    monthly_sorted = dict(sorted(monthly_totals.items())[-6:])

    return render_template(
        "analysis_charts.html",
        category_labels=list(category_totals.keys()),
        category_values=list(category_totals.values()),
        month_labels=list(monthly_sorted.keys()),
        month_values=list(monthly_sorted.values()),
    )


@analysis_bp.route("/analysis/budget", methods=["GET", "POST"])
@login_required
def budget():
    if request.method == "POST":
        category_id = int(request.form.get("category_id"))
        monthly_limit = float(request.form.get("monthly_limit"))

        existing = Budget.query.filter_by(user_id=current_user.id, category_id=category_id).first()
        if existing:
            existing.monthly_limit = monthly_limit
        else:
            db.session.add(Budget(user_id=current_user.id, category_id=category_id, monthly_limit=monthly_limit))
        db.session.commit()
        flash("Budget saved.", "success")
        return redirect(url_for("analysis.budget"))

    categories = Category.query.all()
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    month_txns = _current_month_transactions(current_user.id)

    spent_by_category = defaultdict(float)
    for t in month_txns:
        if t.type == "expense" and t.category_id:
            spent_by_category[t.category_id] += t.amount

    budget_status = []
    for b in budgets:
        spent = spent_by_category.get(b.category_id, 0)
        budget_status.append({
            "category": b.category.name,
            "limit": b.monthly_limit,
            "spent": spent,
            "over": spent > b.monthly_limit,
            "pct": min(100, round((spent / b.monthly_limit) * 100)) if b.monthly_limit else 0,
        })

    return render_template("budget.html", categories=categories, budget_status=budget_status)


@analysis_bp.route("/analysis/report")
@login_required
def report():
    """Report Generation sub-module: exports all transactions as a downloadable CSV."""
    txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Merchant", "Amount", "Type", "Category", "Source"])
    for t in txns:
        writer.writerow([
            t.date.strftime("%Y-%m-%d"),
            t.merchant,
            t.amount,
            t.type,
            t.category.name if t.category else "Uncategorized",
            t.source,
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=expense_report.csv"},
    )


@analysis_bp.route("/analysis/report/view")
@login_required
def report_view():
    txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    return render_template("report.html", transactions=txns)