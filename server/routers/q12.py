
from datetime import date, datetime, timedelta
from typing import Annotated

from calendar import monthrange
from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database


router = APIRouter()



#Clientes sin ventas registradas en el último año.


@router.get("/q12")
async def q12(  db: Annotated[AsyncDatabase, Depends(get_mongo_database)],) -> list[dict]:
    """
    **Propósito:** Listar los clientes sin ventas en el ultimo ano.

    **Valor de retorno:** Lista de clientes sin vebtas en el periodo.

    **Motor utilizado:** MongoDB.
    """

    hoy = date.today()
    dia = min(hoy.day, monthrange(hoy.year - 1, hoy.month)[1])

    desde = datetime(hoy.year - 1, hoy.month, dia)
    hasta = datetime.combine(hoy + timedelta(days=1), datetime.min.time())



    pipeline = [
        {
            "$lookup": {
                "from": "ventas",
                "localField": "_id",
                "foreignField": "id_cliente",
                "pipeline":[{"$match": {"fecha": {"$gte": desde, "$lt": hasta}}},
                    {"$limit": 1},],
                    "as":"ventas_del_periodo"
            }
        },
        {"$match": {"ventas_del_periodo": []}},
        {"$unset": "ventas_del_periodo"},
    ]

    cursor = await db["clientes"].aggregate(pipeline)
    return await cursor.to_list()