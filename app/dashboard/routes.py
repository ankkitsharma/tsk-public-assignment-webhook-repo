from flask import Blueprint, current_app, render_template, jsonify

from app.extensions import mongo
from app.webhook.routes import ACTION_PUSH, ACTION_PULL_REQUEST, ACTION_MERGE

dashboard = Blueprint("Dashboard", __name__, url_prefix="/")


def _get_db():
    """Helper function to get MongoDB database instance."""
    try:
        db = mongo.db
        if db is None and mongo.cx is not None:
            db_name = current_app.config.get("MONGO_DBNAME", "webhook_db")
            db = mongo.cx[db_name]
        return db
    except Exception as e:
        print(f"ERROR accessing MongoDB: {e}")
        return None


def _format_timestamp_for_display(timestamp_str):
    """Format UTC datetime string to '1st April 2021 - 9:30 PM UTC' style."""
    if not timestamp_str:
        return "unknown time"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        day = dt.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

        date_str = f"{day}{suffix} {dt.strftime('%B %Y')}"

        hour_12 = int(dt.strftime("%I"))  # 01-12 as int
        time_str = f"{hour_12}:{dt:%M} {dt:%p}"

        return f"{date_str} - {time_str} UTC"
    except (ValueError, TypeError) as e:
        print(f"Error formatting timestamp {timestamp_str}: {e}")
        return timestamp_str or "unknown time"


@dashboard.route("/", methods=["GET"])
def index():
    """Serve the dashboard HTML page."""
    return render_template("dashboard.html")


@dashboard.route("/api/events", methods=["GET"])
def get_events():
    """API endpoint to fetch latest events from MongoDB."""
    try:
        db = _get_db()
        if db is None:
            return jsonify({"error": "Database not available"}), 500

        events = list(db.events.find().sort("timestamp", -1).limit(50))

        formatted_events = []
        for event in events:
            formatted_event = {
                "id": str(event.get("_id", "")),
                "request_id": event.get("request_id", ""),
                "author": event.get("author", "Unknown"),
                "action": event.get("action", ""),
                "from_branch": event.get("from_branch", ""),
                "to_branch": event.get("to_branch", ""),
                "timestamp": event.get("timestamp", ""),
                "formatted_timestamp": _format_timestamp_for_display(
                    event.get("timestamp", "")
                ),
                "display_message": _format_event_message(event),
            }
            formatted_events.append(formatted_event)

        return jsonify({"events": formatted_events}), 200

    except Exception as e:
        print(f"Error fetching events: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _format_event_message(event):
    """Format event data into display message."""
    author = event.get("author", "Unknown")
    action = event.get("action", "")
    from_branch = event.get("from_branch", "")
    to_branch = event.get("to_branch", "")
    formatted_timestamp = _format_timestamp_for_display(event.get("timestamp", ""))

    if action == ACTION_PUSH:
        return f'"{author}" pushed to "{to_branch}" on {formatted_timestamp}'
    elif action == ACTION_PULL_REQUEST:
        return f'"{author}" submitted a pull request from "{from_branch}" to "{to_branch}" on {formatted_timestamp}'
    elif action == ACTION_MERGE:
        return f'"{author}" merged branch "{from_branch}" to "{to_branch}" on {formatted_timestamp}'
    else:
        return f'"{author}" performed action "{action}" on {formatted_timestamp}'
