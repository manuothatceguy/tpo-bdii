import json
import logging
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

from .stock import clave_saga_pendiente, devolver_stock

logger = logging.getLogger("uvicorn.error")

CREADO = "Creado"
REDIS_DESCONTADO = "Redis descontado"
COMPLETADO = "Completado"
COMPENSADO = "Compensado"
RECHAZADO = "Rechazado"

TIEMPO_LIMITE = timedelta(minutes=5)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _paso(estado: str, motivo: str | None = None) -> dict:
    paso = {"estado": estado, "fecha": _ahora()}
    if motivo is not None:
        paso["motivo"] = motivo
    return paso


async def crear_saga(db: AsyncDatabase, id_sucursal: str, plan: list[dict]) -> ObjectId:
    """
    **Propósito:** Registrar una nueva saga de venta en estado 'Creado' con el
    plan de descuento de stock.

    **Parámetros:** `db`, base de MongoDB; `id_sucursal`, sucursal de los
    lotes; `plan`, lotes y cantidades que se prevé descontar.

    **Valor de retorno:** ID del registro de saga creado.

    **Motor utilizado:** MongoDB.
    """
    ahora = _ahora()
    resultado = await db["sagas"].insert_one(
        {
            "estado": CREADO,
            "id_sucursal": id_sucursal,
            "id_venta": None,
            "plan": plan,
            "lotes_descontados": [],
            "creado": ahora,
            "pasos": [{"estado": CREADO, "fecha": ahora}],
        }
    )
    return resultado.inserted_id


async def marcar_redis_descontado(db: AsyncDatabase, id_saga: ObjectId, lotes: list[dict]) -> None:
    """
    **Propósito:** Pasar la saga a 'Redis descontado' guardando los lotes
    efectivamente descontados, que son los que se usan para compensar.

    **Parámetros:** `db`, base de MongoDB; `id_saga`, registro de saga;
    `lotes`, lotes y cantidades descontados en Redis.

    **Valor de retorno:** Ninguno.

    **Motor utilizado:** MongoDB.
    """
    await db["sagas"].update_one(
        {"_id": id_saga, "estado": CREADO},
        {
            "$set": {"estado": REDIS_DESCONTADO, "lotes_descontados": lotes},
            "$push": {"pasos": _paso(REDIS_DESCONTADO)},
        },
    )


async def marcar_rechazado(db: AsyncDatabase, id_saga: ObjectId, motivo: str) -> None:
    """
    **Propósito:** Pasar la saga a 'Rechazado' cuando el descuento de stock no
    se pudo hacer y por lo tanto no hay nada que compensar.

    **Parámetros:** `db`, base de MongoDB; `id_saga`, registro de saga;
    `motivo`, causa del rechazo.

    **Valor de retorno:** Ninguno.

    **Motor utilizado:** MongoDB.
    """
    await db["sagas"].update_one(
        {"_id": id_saga, "estado": CREADO},
        {"$set": {"estado": RECHAZADO}, "$push": {"pasos": _paso(RECHAZADO, motivo)}},
    )


async def marcar_completado(db: AsyncDatabase, id_saga: ObjectId, id_venta: str, session) -> bool:
    """
    **Propósito:** Pasar la saga de 'Redis descontado' a 'Completado' dentro
    de la transacción que inserta la venta.

    **Parámetros:** `db`, base de MongoDB; `id_saga`, registro de saga;
    `id_venta`, venta creada; `session`, sesión de la transacción.

    **Valor de retorno:** `True` si la saga seguía en 'Redis descontado' y se
    actualizó, `False` si ya había sido compensada.

    **Motor utilizado:** MongoDB.
    """
    resultado = await db["sagas"].update_one(
        {"_id": id_saga, "estado": REDIS_DESCONTADO},
        {
            "$set": {"estado": COMPLETADO, "id_venta": id_venta},
            "$push": {"pasos": _paso(COMPLETADO)},
        },
        session=session,
    )
    return resultado.modified_count == 1


async def compensar_saga(db: AsyncDatabase, redis: Redis, id_saga: ObjectId, motivo: str) -> bool:
    """
    **Propósito:** Compensar el paso de Redis de una saga devolviendo las
    unidades descontadas. Primero pasa la saga de 'Redis descontado' a
    'Compensado' con una actualización condicional, así la devolución ocurre
    una sola vez y nunca sobre una venta que llegó a confirmarse.

    **Parámetros:** `db`, base de MongoDB; `redis`, cliente de Redis;
    `id_saga`, registro de saga; `motivo`, causa de la compensación.

    **Valor de retorno:** `True` si se devolvió el stock, `False` si la saga no
    estaba en 'Redis descontado'.

    **Motor utilizado:** MongoDB y Redis.
    """
    saga = await db["sagas"].find_one_and_update(
        {"_id": id_saga, "estado": REDIS_DESCONTADO},
        {"$set": {"estado": COMPENSADO}, "$push": {"pasos": _paso(COMPENSADO, motivo)}},
        return_document=ReturnDocument.AFTER,
    )
    if saga is None:
        return False
    try:
        await devolver_stock(redis, saga["lotes_descontados"])
    except Exception:
        await db["sagas"].update_one(
            {"_id": id_saga, "estado": COMPENSADO},
            {
                "$set": {"estado": REDIS_DESCONTADO},
                "$push": {"pasos": _paso(REDIS_DESCONTADO, "Falló la devolución de stock")},
            },
        )
        raise
    try:
        await redis.delete(clave_saga_pendiente(str(id_saga)))
    except Exception:
        pass
    return True


async def recuperar_sagas(db: AsyncDatabase, redis: Redis) -> list[ObjectId]:
    """
    **Propósito:** Compensar las sagas que quedaron trabadas en 'Redis
    descontado' o en 'Creado' por más de `TIEMPO_LIMITE` desde su creación,
    por ejemplo porque la aplicación se cayó durante la ejecución de la saga.

    **Parámetros:** `db`, base de MongoDB; `redis`, cliente de Redis.

    **Valor de retorno:** Lista con los IDs de las sagas compensadas.

    **Motor utilizado:** MongoDB y Redis.
    """
    limite = _ahora() - TIEMPO_LIMITE
    compensadas = []

    cursor = db["sagas"].find({"estado": REDIS_DESCONTADO, "creado": {"$lt": limite}}, {"_id": 1})
    async for saga in cursor:
        try:
            if await compensar_saga(db, redis, saga["_id"], "Recuperación al iniciar: saga trabada"):
                compensadas.append(saga["_id"])
        except Exception as error:
            logger.warning("No se pudo compensar la saga %s: %s", saga["_id"], error)

    cursor_creadas = db["sagas"].find({"estado": CREADO, "creado": {"$lt": limite}}, {"_id": 1})
    async for saga in cursor_creadas:
        try:
            clave_pendiente = clave_saga_pendiente(str(saga["_id"]))
            raw = await redis.get(clave_pendiente)
            if raw is not None:
                lotes = json.loads(raw)
                actualizada = await db["sagas"].find_one_and_update(
                    {"_id": saga["_id"], "estado": CREADO},
                    {
                        "$set": {"estado": COMPENSADO, "lotes_descontados": lotes},
                        "$push": {
                            "pasos": _paso(
                                COMPENSADO,
                                "Recuperación al iniciar: saga Creado con descuento en Redis",
                            )
                        },
                    },
                    return_document=ReturnDocument.AFTER,
                )
                if actualizada is not None:
                    try:
                        await devolver_stock(redis, lotes)
                    except Exception:
                        await db["sagas"].update_one(
                            {"_id": saga["_id"], "estado": COMPENSADO},
                            {
                                "$set": {"estado": REDIS_DESCONTADO},
                                "$push": {"pasos": _paso(REDIS_DESCONTADO, "Falló la devolución de stock")},
                            },
                        )
                        raise
                    try:
                        await redis.delete(clave_pendiente)
                    except Exception:
                        pass
                    compensadas.append(saga["_id"])
            else:
                await db["sagas"].find_one_and_update(
                    {"_id": saga["_id"], "estado": CREADO},
                    {
                        "$set": {"estado": RECHAZADO},
                        "$push": {
                            "pasos": _paso(
                                RECHAZADO,
                                "Recuperación al iniciar: saga expirada sin descuento en Redis",
                            )
                        },
                    },
                )
        except Exception as error:
            logger.warning("No se pudo recuperar la saga %s: %s", saga["_id"], error)

    return compensadas
