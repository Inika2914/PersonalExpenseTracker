import pandas as pd
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from models import db
from models.transaction import Transaction
from models.category import Category
from services.parser import parse_transaction_text
from services.categorize import categorize

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@transactions_bp.route("/")
@login_required
def list_transactions():
    txns = (Transaction.query
            .filter_by(user_id=current_user.id)
            .order_by(Transaction.date.desc())
            .all())
    categories = Category.query.all()
    return render_template("transactions_list.html", transactions=txns, categories=categories)


@transactions_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_manual():
    if request.method == "POST":
        amount = float(request.form.get("amount", 0))
        ttype = request.form.get("type", "expense")
        merchant = request.form.get("merchant", "").strip()

        category = categorize(merchant, "", ttype)
        txn = Transaction(
            user_id=current_user.id,
            amount=amount,
            type=ttype,
            merchant=merchant,
            category_id=category.id if category else None,
            source="manual",
        )
        db.session.add(txn)
        db.session.commit()
        flash("Transaction added.", "success")
        return redirect(url_for("transactions.list_transactions"))

    return render_template("transactions_add.html")


@transactions_bp.route("/simulate", methods=["GET", "POST"])
@login_required
def simulate():
    """
    Test harness standing in for the future Android SMS/notification
    capture. Paste in raw SMS or notification text, choose the source,
    and it runs through the SAME parser + categorizer that will later
    be fed by the real BroadcastReceiver / NotificationListenerService.
    """
    parsed_preview = None

    if request.method == "POST":
        raw_text = request.form.get("raw_text", "").strip()
        source = request.form.get("source", "sms")  # "sms" or "notification"

        parsed = parse_transaction_text(raw_text, source=source)

        if not parsed:
            flash("That text doesn't look like a payment message - couldn't extract a transaction.", "danger")
            return render_template("transactions_simulate.html", parsed_preview=None)

        category = categorize(parsed["merchant"], raw_text, parsed["type"])
        txn = Transaction(
            user_id=current_user.id,
            amount=parsed["amount"],
            type=parsed["type"],
            merchant=parsed["merchant"],
            category_id=category.id if category else None,
            source=parsed["source"],
            raw_text=parsed["raw_text"],
        )
        db.session.add(txn)
        db.session.commit()

        parsed_preview = parsed
        parsed_preview["category"] = category.name if category else "Others"
        flash(f"Simulated {source} captured and categorized as {parsed_preview['category']}.", "success")

    return render_template("transactions_simulate.html", parsed_preview=parsed_preview)


@transactions_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_statement():
    """
    Secondary capture path: bulk-import a bank statement (CSV/Excel).
    Expects columns: amount, type, merchant, date (flexible naming
    handled loosely below - a real bank export may need column mapping,
    kept simple here for the mini-project scope).
    """
    if request.method == "POST":
        file = request.files.get("statement")
        if not file or file.filename == "":
            flash("Please choose a CSV or Excel file.", "danger")
            return redirect(url_for("transactions.upload_statement"))

        try:
            if file.filename.lower().endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            flash(f"Could not read file: {e}", "danger")
            return redirect(url_for("transactions.upload_statement"))

        df.columns = [c.strip().lower() for c in df.columns]
        added = 0

        for _, row in df.iterrows():
            amount = row.get("amount")
            if pd.isna(amount):
                continue
            merchant = str(row.get("merchant", "")).strip()
            ttype = str(row.get("type", "expense")).strip().lower()
            if ttype not in ("income", "expense"):
                ttype = "expense"

            category = categorize(merchant, "", ttype)
            txn = Transaction(
                user_id=current_user.id,
                amount=float(amount),
                type=ttype,
                merchant=merchant,
                category_id=category.id if category else None,
                source="csv_upload",
            )
            db.session.add(txn)
            added += 1

        db.session.commit()
        flash(f"Imported {added} transactions from statement.", "success")
        return redirect(url_for("transactions.list_transactions"))

    return render_template("transactions_upload.html")


@transactions_bp.route("/<int:txn_id>/category", methods=["POST"])
@login_required
def update_category(txn_id):
    txn = Transaction.query.filter_by(id=txn_id, user_id=current_user.id).first_or_404()
    category_id = request.form.get("category_id")
    txn.category_id = int(category_id) if category_id else None
    db.session.commit()
    flash("Category updated.", "success")
    return redirect(url_for("transactions.list_transactions"))


@transactions_bp.route("/<int:txn_id>/delete", methods=["POST"])
@login_required
def delete_transaction(txn_id):
    txn = Transaction.query.filter_by(id=txn_id, user_id=current_user.id).first_or_404()
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted.", "info")
    return redirect(url_for("transactions.list_transactions"))
