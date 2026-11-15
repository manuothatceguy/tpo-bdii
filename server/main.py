import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError

from .dependencies.mongo import MONGO_DB, create_mongo_client
from .dependencies.redis import create_redis_client
from .routers import clientes, farmaceuticos, productos, recetas, stock, sucursales, ventas
from .servicios.saga import recuperar_sagas

logger = logging.getLogger("uvicorn.error")
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo = create_mongo_client()
    app.state.redis = create_redis_client()
    try:
        compensadas = await recuperar_sagas(app.state.mongo[MONGO_DB], app.state.redis)
        if compensadas:
            logger.info("Sagas trabadas compensadas: %s", ", ".join(map(str, compensadas)))
    except (PyMongoError, RedisError) as error:
        logger.warning("No se pudo ejecutar la recuperación de sagas: %s", error)
    yield
    await app.state.mongo.close()
    await app.state.redis.aclose()


app = FastAPI(title="FarmaRed", lifespan=lifespan)


@app.get("/", include_in_schema=False)
async def interfaz_web() -> FileResponse:
    return FileResponse(INDEX_HTML)


for modulo in (productos, ventas, clientes, recetas, farmaceuticos, sucursales, stock):
    app.include_router(modulo.router)

app.mount("/temas", StaticFiles(directory=STATIC_DIR / "temas"), name="temas")
