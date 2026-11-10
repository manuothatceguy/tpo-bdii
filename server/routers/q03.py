from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

# Historial completo de un cliente: ventas y recetas ordenadas por fecha.

@router.get("/q03")
async def q03(
    id_cliente: str,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> dict:
    """
    **Propósito:** Consultar el historial completo de ventas y recetas de un
    cliente, ordenado cronológicamente de más antiguo a más reciente.

    **Parámetros:** `id_cliente`, identificador del cliente a consultar.

    **Valor de retorno:** Devuelve un diccionario con el ID del cliente y 
    su historial de ventas y recetas ordenado por fecha. Cada evento incluye 
    el tipo, la fecha y sus datos completos.

    **Motor utilizado:** MongoDB.
    """
    if await db["clientes"].find_one({"_id": id_cliente}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    pipeline = [
        {"$match": {"id_cliente": id_cliente}},
        {
            "$project": {
                "_id": 0,
                "tipo": {"$literal": "venta"},
                "fecha": "$fecha",
                "datos": "$$ROOT",
            }
        },
        {
            "$unionWith": {
                "coll": "recetas",
                "pipeline": [
                    {"$match": {"id_cliente": id_cliente}},
                    {
                        "$project": {
                            "_id": 0,
                            "tipo": {"$literal": "receta"},
                            "fecha": "$fecha_emision",
                            "datos": "$$ROOT",
                        }
                    },
                ],
            }
        },
        {"$sort": {"fecha": 1, "tipo": 1, "datos._id": 1}},
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return {"id_cliente": id_cliente, "historial": await cursor.to_list()}
