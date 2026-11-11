from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

# Ingresos totales por farmacéutico en el mes actual, solo ventas completadas


@router.get("/q11")
async def q11(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Obtener los ingresos totales de cada farmacéutico en el mes
    actual, considerando solo ventas en estado 'Completada'.

    **Valor de retorno:** Lista de farmacéuticos con su ID, nombre, apellido,
    matrícula, sucursal, cantidad de ventas e ingresos totales, ordenada de
    mayor a menor ingreso.

    **Motor utilizado:** MongoDB.
    """
    hoy = date.today()
    desde = datetime.combine(hoy.replace(day=1), datetime.min.time())
    hasta = datetime.combine(hoy + timedelta(days=1), datetime.min.time())

    pipeline = [
        {
            "$match": {
                "estado": "Completada",
                "fecha": {"$gte": desde, "$lt": hasta},
            }
        },
        {
            "$group": {
                "_id": "$id_farmaceutico",
                "cantidad_ventas": {"$sum": 1},
                "ingresos_totales": {"$sum": "$total"},
            }
        },
        {
            "$lookup": {
                "from": "farmaceuticos",
                "localField": "_id",
                "foreignField": "_id",
                "as": "farmaceutico",
            }
        },
        {"$unwind": "$farmaceutico"},
        {
            "$project": {
                "_id": 0,
                "id_farmaceutico": "$_id",
                "nombre": "$farmaceutico.nombre",
                "apellido": "$farmaceutico.apellido",
                "matricula": "$farmaceutico.matricula",
                "id_sucursal": "$farmaceutico.id_sucursal",
                "cantidad_ventas": 1,
                "ingresos_totales": 1,
            }
        },
        {"$sort": {"ingresos_totales": -1, "id_farmaceutico": 1}},
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return await cursor.to_list()
