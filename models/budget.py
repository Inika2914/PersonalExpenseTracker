from models import db


class Budget(db.Model):
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)

    category = db.relationship("Category")

    def __repr__(self):
        return f"<Budget cat={self.category_id} limit={self.monthly_limit}>"
