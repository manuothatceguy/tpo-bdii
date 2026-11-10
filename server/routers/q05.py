from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

@router.get("/q05")
async def q05(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar los farmacéuticos activos con la cantidad de ventas
    que registraron en los últimos 60 días, sin contar las anuladas. Los
    farmacéuticos sin ventas en ese período aparecen con cero.

    **Valor de retorno:** Lista de farmacéuticos con su ID, nombre, apellido,
    matrícula, sucursal y cantidad de ventas, ordenada de mayor a menor
    cantidad.

    **Motor utilizado:** MongoDB.
    """

    hoy = date.today()
    desde = datetime.combine(hoy - timedelta(days=60), datetime.min.time())
    hasta = datetime.combine(hoy + timedelta(days=1), datetime.min.time())

    pipeline = [
        {"$match": {"activo": True}},
        {
            "$lookup": {
                "from": "ventas",
                "localField": "_id",
                "foreignField": "id_farmaceutico",
                "pipeline": [
                    {
                        "$match": {
                            "fecha": {"$gte": desde, "$lt": hasta},
                            "estado": {"$ne": "Anulada"},
                        }
                    },
                    {"$project": {"_id": 1}},
                ],
                "as": "ventas",
            }
        },
        {
            "$project": {
                "_id": 0,
                "id_farmaceutico": "$_id",
                "nombre": 1,
                "apellido": 1,
                "matricula": 1,
                "id_sucursal": 1,
                "cantidad_ventas": {"$size": "$ventas"},
            }
        },
        {"$sort": {"cantidad_ventas": -1, "id_farmaceutico": 1}},
    ]

    cursor = await db["farmaceuticos"].aggregate(pipeline)
    return await cursor.to_list()
