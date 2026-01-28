from datetime import datetime
from flask import Blueprint, current_app, json, request

from app.extensions import mongo

webhook = Blueprint("Webhook", __name__, url_prefix="/webhook")

# Action enum values for the schema
ACTION_PUSH = "PUSH"
ACTION_PULL_REQUEST = "PULL_REQUEST"
ACTION_MERGE = "MERGE"


def _timestamp_to_utc_datetime_string(iso_timestamp):
    """Convert ISO timestamp to UTC datetime string (e.g. '2021-04-01T21:30:00Z')."""
    if not iso_timestamp:
        return ""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return iso_timestamp or ""


@webhook.route("/", methods=["GET"])
def root():
    return json.jsonify({"message": "Webhook receiver is running"}), 200


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
        import traceback

        traceback.print_exc()
        return None


@webhook.route("/receiver", methods=["POST"])
def receiver():
    event = (
        request.headers.get("X-GitHub-Event", "")
        or request.headers.get("x-github-event", "")
        or request.headers.get("X-GITHUB-EVENT", "")
    )
    data = request.get_json(silent=True) or {}

    if not event and isinstance(data, dict):
        if "ref" in data and "commits" in data:
            event = "push"
            print("Inferred event type 'push' from payload structure")
        elif "pull_request" in data:
            event = "pull_request"
            print("Inferred event type 'pull_request' from payload structure")

    print(f"Received webhook event: '{event}'")

    db = _get_db()
    if db is None:
        print(
            "ERROR: MongoDB database is None! Check MONGO_URI and MONGO_DBNAME configuration."
        )
        return json.jsonify(
            {"message": "Webhook received", "error": "Database not initialized"}
        ), 500

    if event == "push":
        print("Processing PUSH event...")
        ref = data.get("ref", "")
        if not ref.startswith("refs/heads/"):
            return json.jsonify({"message": "Webhook received"}), 200
        head_commit = data.get("head_commit")
        if not head_commit:
            return json.jsonify({"message": "Webhook received"}), 200
        to_branch = ref.replace("refs/heads/", "")
        author = (
            (data.get("pusher") or {}).get("name")
            or (data.get("sender") or {}).get("login")
            or "Unknown"
        )
        raw_ts = head_commit.get("timestamp") or (head_commit.get("author") or {}).get(
            "date"
        )
        request_id = head_commit.get("id", "")
        doc = {
            "request_id": request_id,
            "author": author,
            "action": ACTION_PUSH,
            "from_branch": "",
            "to_branch": to_branch,
            "timestamp": _timestamp_to_utc_datetime_string(raw_ts),
        }
        try:
            result = db.events.insert_one(doc)
            print(f"Inserted PUSH event with _id: {result.inserted_id}")
        except Exception as e:
            print(f"Error inserting PUSH event: {e}")
            import traceback

            traceback.print_exc()

    elif event == "pull_request":
        print("Processing PULL_REQUEST event...")
        action = data.get("action")
        pr = data.get("pull_request") or {}
        from_branch = (pr.get("head") or {}).get("ref", "")
        to_branch = (pr.get("base") or {}).get("ref", "")
        author = (data.get("sender") or {}).get("login") or "Unknown"
        request_id = str(pr.get("number", ""))

        if pr.get("merged") and action == "closed":
            raw_ts = pr.get("merged_at")
            doc = {
                "request_id": request_id,
                "author": author,
                "action": ACTION_MERGE,
                "from_branch": from_branch,
                "to_branch": to_branch,
                "timestamp": _timestamp_to_utc_datetime_string(raw_ts),
            }
            try:
                result = db.events.insert_one(doc)
                print(f"Inserted MERGE event with _id: {result.inserted_id}")
            except Exception as e:
                print(f"Error inserting MERGE event: {e}")
                import traceback

                traceback.print_exc()
        elif action == "opened":
            raw_ts = pr.get("created_at")
            doc = {
                "request_id": request_id,
                "author": author,
                "action": ACTION_PULL_REQUEST,
                "from_branch": from_branch,
                "to_branch": to_branch,
                "timestamp": _timestamp_to_utc_datetime_string(raw_ts),
            }
            try:
                result = db.events.insert_one(doc)
                print(f"Inserted PULL_REQUEST event with _id: {result.inserted_id}")
            except Exception as e:
                print(f"Error inserting PULL_REQUEST event: {e}")
                import traceback

                traceback.print_exc()
        else:
            return json.jsonify({"message": "Webhook received"}), 200

    else:
        print(f"Unknown or empty event type: '{event}'. Returning without saving.")
        print(
            f"Available headers with 'event' or 'github': {[k for k in request.headers.keys() if 'event' in k.lower() or 'github' in k.lower()]}"
        )
        return json.jsonify({"message": "Webhook received"}), 200

    return json.jsonify({"message": "Webhook received"}), 200
