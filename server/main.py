from contextlib import asynccontextmanager

from fastapi import FastAPI

from .dependencies.mongo import create_mongo_client
from .dependencies.redis import create_redis_client
from .routers import clientes, farmaceuticos, productos, recetas, stock, sucursales, ventas


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo = create_mongo_client()
    app.state.redis = create_redis_client()
    yield
    await app.state.mongo.close()
    await app.state.redis.aclose()


app = FastAPI(title="FarmaRed", lifespan=lifespan)

for modulo in (productos, ventas, clientes, recetas, farmaceuticos, sucursales, stock):
    app.include_router(modulo.router)
