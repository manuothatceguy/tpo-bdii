from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

# Clientes con más de una receta registrada, indicando la cantidad.

@router.get("/q04")
async def q04(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar los clientes con más de una receta registrada,
    contando recetas de cualquier estado e incluyendo clientes inactivos.

    **Valor de retorno:** Lista de clientes con su ID, nombre, apellido y
    cantidad de recetas registradas.

    **Motor utilizado:** MongoDB.
    """
    pipeline = [
        {
            "$group": {
                "_id": "$id_cliente",
                "cantidad_recetas": {"$sum": 1},
            }
        },
        {"$match": {"cantidad_recetas": {"$gt": 1}}},
        {
            "$lookup": {
                "from": "clientes",
                "localField": "_id",
                "foreignField": "_id",
                "as": "cliente",
            }
        },
        {"$unwind": "$cliente"},
        {
            "$project": {
                "_id": 0,
                "id_cliente": "$_id",
                "nombre": "$cliente.nombre",
                "apellido": "$cliente.apellido",
                "cantidad_recetas": 1,
            }
        },
    ]

    cursor = await db["recetas"].aggregate(pipeline)
    return await cursor.to_list()
