from datetime import datetime
from models import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)           # "income" or "expense"
    merchant = db.Column(db.String(150), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    # Where this row came from: "sms", "notification", "csv_upload", "manual"
    source = db.Column(db.String(20), default="manual")
    raw_text = db.Column(db.Text, nullable=True)               # original SMS/notification text, for debugging

    def __repr__(self):
        return f"<Transaction {self.amount} {self.type} ({self.source})>"
