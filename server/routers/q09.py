from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

# Ventas de tipo Venta libre con total menor a 5.000.


@router.get("/q09")
async def q09(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar las ventas de tipo 'Venta libre' cuyo total es menor
    a $5.000 ARS, excluyendo aquellas en estado 'Anulada'.

    **Valor de retorno:** Lista de ventas que cumplen la condición, ordenada por
    fecha y por ID de venta.

    **Motor utilizado:** MongoDB.
    """
    pipeline = [
        {
            "$match": {
                "tipo": "Venta libre",
                "total": {"$lt": 5000},
                "estado": {"$ne": "Anulada"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "id_venta": "$_id",
                "id_cliente": 1,
                "id_farmaceutico": 1,
                "id_sucursal": 1,
                "fecha": 1,
                "tipo": 1,
                "medio_pago": 1,
                "total": 1,
                "estado": 1,
                "items": 1,
            }
        },
        {"$sort": {"fecha": 1, "id_venta": 1}},
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return await cursor.to_list()
