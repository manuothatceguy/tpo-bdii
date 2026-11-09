from contextlib import asynccontextmanager

from fastapi import FastAPI

from .dependencies.mongo import create_mongo_client
from .dependencies.redis import create_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo = create_mongo_client()
    app.state.redis = create_redis_client()
    yield
    await app.state.mongo.close()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
