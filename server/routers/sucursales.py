from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter(prefix="/sucursales", tags=["Sucursales"])


@router.get("/{id_sucursal}/clientes", summary="Q10 · Clientes atendidos en una sucursal")
async def clientes_de_sucursal(
    id_sucursal: str,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar todos los clientes atendidos en una sucursal, a
    través del farmacéutico que registró la venta, esté activo o no.

    **Parámetros:** `id_sucursal`, identificador de la sucursal a consultar.

    **Valor de retorno:** Lista de clientes sin repetir, con sus datos y la
    cantidad de ventas que tuvieron en la sucursal, ordenada por ID de cliente.

    **Motor utilizado:** MongoDB.
    """
    if await db["sucursales"].find_one({"_id": id_sucursal}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    pipeline = [
        {"$match": {"id_sucursal": id_sucursal}},
        {"$group": {"_id": "$id_cliente", "cantidad_ventas": {"$sum": 1}}},
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
                "dni": "$cliente.dni",
                "email": "$cliente.email",
                "telefono": "$cliente.telefono",
                "obra_social": "$cliente.obra_social",
                "activo": "$cliente.activo",
                "cantidad_ventas": 1,
            }
        },
        {"$sort": {"id_cliente": 1}},
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return await cursor.to_list()
