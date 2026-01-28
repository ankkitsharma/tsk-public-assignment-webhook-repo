from flask import Flask

from app.extensions import mongo, MONGO_URI
from app.webhook.routes import webhook


# Creating our flask app
def create_app():
    app = Flask(__name__)

    app.config["MONGO_URI"] = MONGO_URI
    app.config.setdefault("MONGO_DBNAME", "webhook_db")
    mongo.init_app(app)
    # registering all the blueprints
    app.register_blueprint(webhook)

    return app
