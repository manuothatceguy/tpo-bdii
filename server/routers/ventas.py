from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.get("/pendientes", summary="Q02 · Ventas pendientes con su farmacéutico")
async def ventas_pendientes(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar las ventas en estado 'Pendiente' con los datos del
    farmacéutico asignado y el total.

    **Valor de retorno:** Lista de ventas pendientes. Cada resultado incluye el
    ID y el total de la venta, y el nombre, apellido, matrícula y sucursal del
    farmacéutico.

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


@router.get("/venta-libre", summary="Q09 · Ventas libres menores a $5.000")
async def ventas_libres_bajo_monto(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar las ventas de tipo 'Venta libre' cuyo total es menor
    a $5.000 ARS, excluyendo las que están en estado 'Anulada'.

    **Valor de retorno:** Lista de ventas que cumplen la condición, ordenada
    por fecha y por ID de venta.

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
