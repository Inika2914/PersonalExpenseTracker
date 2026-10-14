"""
Turns one raw captured message (SMS or UPI notification) into a Transaction.

Used by POST /api/transactions/raw, i.e. by the Android app. Responsibilities:
  1. parse the text (services.parser)            -> ignore OTPs, failed payments, promos
  2. de-duplicate                                 -> the same payment often arrives twice
  3. categorize and save                          -> services.categorize

Reliability design (decided earlier in the project): the bank SMS is the source of
truth for "did it happen and for how much"; the UPI app notification usually has the
cleaner merchant name. When both arrive for the same payment they are MERGED into one
transaction instead of being counted twice.
"""
from datetime import datetime, timedelta, timezone

from models import db
from models.transaction import Transaction
from services.parser import parse_transaction_text
from services.categorize import categorize

MERGE_WINDOW = timedelta(minutes=2)


def _ms_to_naive_utc(ms):
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)


def ingest_raw(user, raw_text, source="sms", sender=None, package=None, received_at_ms=None):
    raw_text = (raw_text or "").strip()
    received = _ms_to_naive_utc(received_at_ms) if received_at_ms else datetime.utcnow()

    parsed = parse_transaction_text(raw_text, source=source, sender=sender,
                                    package=package, received_at=received)
    if not parsed:
        return {"status": "ignored", "reason": "not_a_payment_message"}

    nearby = (Transaction.query
              .filter(Transaction.user_id == user.id,
                      Transaction.type == parsed["type"],
                      Transaction.date >= received - MERGE_WINDOW,
                      Transaction.date <= received + MERGE_WINDOW,
                      db.func.abs(Transaction.amount - parsed["amount"]) < 0.005)
              .all())

    for existing in nearby:
        if (existing.raw_text or "").strip() == raw_text:
            return {"status": "duplicate", "id": existing.id}

        # Same payment seen through the other channel (SMS <-> notification): merge.
        if existing.source != source and existing.source in ("sms", "notification"):
            if parsed["merchant"] != "Unknown" and (not existing.merchant or existing.merchant == "Unknown"):
                existing.merchant = parsed["merchant"]
                if existing.category is None or existing.category.name == "Others":
                    better = categorize(existing.merchant, raw_text, existing.type)
                    existing.category_id = better.id if better else None
                db.session.commit()
            return {"status": "merged", "id": existing.id, "merchant": existing.merchant}

    category = categorize(parsed["merchant"], raw_text, parsed["type"])
    txn = Transaction(
        user_id=user.id,
        amount=parsed["amount"],
        type=parsed["type"],
        merchant=parsed["merchant"],
        category_id=category.id if category else None,
        date=received,
        source=source,
        raw_text=raw_text,
    )
    db.session.add(txn)
    db.session.commit()
    return {
        "status": "created", "id": txn.id, "amount": txn.amount, "type": txn.type,
        "merchant": txn.merchant, "category": category.name if category else None,
    }
