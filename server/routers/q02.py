from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

#Ventas en estado 'Pendiente' con el farmacéutico asignado (nombre, matrícula y sucursal) y el total

@router.get("/q02")
async def q02(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:

    """
    **Propósito:** Listar las ventas en estado pendiente con los datos del
    farmacéutico asignado y el total.

    **Valor de retorno:** Lista de ventas pendientes. Cada resultado incluye
    el ID, el total de la ventanta. Tambien el nombre, apellido, matrícula y sucursal
    del farmacéutico.

    **Motor utilizado:** MongoDB.
    """
   
    pipeline = [
        {"$match": {"estado": "Pendiente"}},
        {
            "$lookup": {
                "from": "farmaceuticos",
                "localField": "id_farmaceutico",
                "foreignField": "_id",
                "as": "farmaceutico",
            }
        },
        {"$unwind": "$farmaceutico"},
        {
            "$lookup": {
                "from": "sucursales",
                "localField": "farmaceutico.id_sucursal",
                "foreignField": "_id",
                "as": "sucursal",
            }
        },
        {"$unwind": "$sucursal"},
        {
            "$project": {
                "_id": 0,
                "id_venta": "$_id",
                "total": 1,
                "farmaceutico": {
                    "nombre": "$farmaceutico.nombre",
                    "apellido": "$farmaceutico.apellido",
                    "matricula": "$farmaceutico.matricula",
                    "sucursal": "$sucursal.nombre",
                },
            }
        },
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return await cursor.to_list()