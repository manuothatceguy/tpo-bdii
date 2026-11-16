from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("/activos", summary="Q01 - Productos activos con su proveedor")
async def productos_activos(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar los productos activos con todos los datos de su
    proveedor.

    **Valor de retorno:** Lista de productos activos. Cada producto incluye
    los datos de su proveedor en el campo `proveedor`.

    **Motor utilizado:** MongoDB.
    """
    pipeline = [
        {"$match": {"activo": True}},
        {
            "$lookup": {
                "from": "proveedores",
                "localField": "id_proveedor",
                "foreignField": "_id",
                "as": "proveedor",
            }
        },
        {"$unwind": {"path": "$proveedor", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"_id": 1}},
    ]

    cursor = await db["productos"].aggregate(pipeline)
    return await cursor.to_list()


@router.get("/mas-vendidos", summary="Q07 - Top 5 productos más vendidos")
async def productos_mas_vendidos(
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
