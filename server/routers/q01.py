#Q1 Lectura Productos activos con todos los datos de su proveedor.



from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

#GET Q01
@router.get("/q01")
async def q01(  db: Annotated[AsyncDatabase, Depends(get_mongo_database)],) -> list[dict]:
    """
    **Propósito:** Listar los productos activos con todos los datos de su proveedor.

    **Valor de retorno:** Lista de productos activos. Cada producto incluye
    el los datos de su proveedor en el campo `proveedor`.

    **Motor utilizado:** MongoDB.
    """
    pipeline = [
        {"$match": {"activo": True}}, #prod activos 
        {
            "$lookup": {
                "from": "proveedores",
                "localField": "id_proveedor",
                "foreignField": "_id",
                "as": "proveedor",
            }
        },
        {"$unwind": "$proveedor"}, #obj(sin lista )
    ]

    cursor = await db["productos"].aggregate(pipeline)
    return await cursor.to_list()