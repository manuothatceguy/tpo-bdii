import os

from dotenv import load_dotenv
from fastapi import Request
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
MONGO_DB = os.getenv("MONGO_DB", "farmared")


def create_mongo_client() -> AsyncMongoClient:
    return AsyncMongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)


def get_mongo_database(request: Request) -> AsyncDatabase:
    return request.app.state.mongo[MONGO_DB]
