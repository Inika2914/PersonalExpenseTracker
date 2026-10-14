from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models.device_token import DeviceToken

capture_bp = Blueprint("capture", __name__)


@capture_bp.route("/capture")
@login_required
def capture_page():
    """Phone capture settings: permissions, status and test tools (works inside the Android app)."""
    linked = DeviceToken.query.filter_by(user_id=current_user.id).count()
    return render_template("capture.html", linked_devices=linked)
