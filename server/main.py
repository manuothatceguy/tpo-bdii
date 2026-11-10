from contextlib import asynccontextmanager

from fastapi import FastAPI

from .dependencies.mongo import create_mongo_client
from .dependencies.redis import create_redis_client
from .routers.q01 import router as q01_router
from .routers.q02 import router as q02_router
from .routers.q03 import router as q03_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo = create_mongo_client()
    app.state.redis = create_redis_client()
    yield
    await app.state.mongo.close()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(q01_router)
app.include_router(q02_router)
app.include_router(q03_router)
