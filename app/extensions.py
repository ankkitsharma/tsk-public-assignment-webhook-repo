import os

from dotenv import load_dotenv
from flask_pymongo import PyMongo

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/database")
mongo = PyMongo()
