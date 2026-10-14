from datetime import datetime
from models import db


class DeviceToken(db.Model):
    """
    A long-lived credential for one linked phone. The Android app uploads captured
    SMS / UPI notifications in the background (no browser session exists then), so it
    authenticates with this token instead. Only a SHA-256 hash is stored.
    """
    __tablename__ = "device_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    device_name = db.Column(db.String(80), default="Android app")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("device_tokens", lazy=True,
                                                      cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<DeviceToken user={self.user_id} {self.device_name}>"
