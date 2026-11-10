from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

# Top 5 productos más vendidos por unidades, solo en ventas completadas.

@router.get("/q07")
async def q07(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Obtener los cinco productos más vendidos por cantidad de
    unidades, considerando únicamente ventas completadas.

    **Valor de retorno:** Lista con el ID de cada producto y sus unidades
    vendidas, ordenada de mayor a menor cantidad. Los empates se ordenan por ID.

    **Motor utilizado:** MongoDB.
    """
    pipeline = [
        {"$match": {"estado": "Completada"}},
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.id_producto",
                "unidades_vendidas": {"$sum": "$items.cantidad"},
            }
        },
        {"$sort": {"unidades_vendidas": -1, "_id": 1}},
        {"$limit": 5},
        {
            "$project": {
                "_id": 0,
                "id_producto": "$_id",
                "unidades_vendidas": 1,
            }
        },
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return await cursor.to_list()
