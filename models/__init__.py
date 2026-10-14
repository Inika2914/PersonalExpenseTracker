from flask_sqlalchemy import SQLAlchemy

# Single shared db instance, imported by every model file and by app.py.
db = SQLAlchemy()

# Import every model here so they are all registered with SQLAlchemy before any
# relationship string (like "Transaction") has to be resolved, and so that
# db.create_all() creates every table (including device_tokens) on startup.
from models.user import User                      # noqa: E402,F401
from models.category import Category              # noqa: E402,F401
from models.transaction import Transaction        # noqa: E402,F401
from models.budget import Budget                  # noqa: E402,F401
from models.device_token import DeviceToken       # noqa: E402,F401
