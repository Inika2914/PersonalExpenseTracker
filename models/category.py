from models import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)          # e.g. "Food", "Travel"
    keywords = db.Column(db.String(500), default="")          # comma-separated, used for auto-categorization

    transactions = db.relationship("Transaction", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"
