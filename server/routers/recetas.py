from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter(prefix="/recetas", tags=["Recetas"])


@router.get("/dispensas-vencidas", summary="Q06 - Tratamientos prolongados con dispensa vencida")
async def recetas_con_dispensa_vencida(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar las recetas de tratamiento prolongado en estado
    'Vigente' cuya próxima dispensa es anterior a hoy, junto con los datos del
    cliente.

    **Valor de retorno:** Lista de recetas ordenada por próxima dispensa. Cada
    resultado incluye los datos de la receta y un objeto con los datos del
    cliente.

    **Motor utilizado:** MongoDB.
    """
    hoy = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time())

    pipeline = [
        {
            "$match": {
                "tipo": "Tratamiento prolongado",
                "estado": "Vigente",
                "proxima_dispensa": {"$lt": hoy},
            }
        },
        {
            "$lookup": {
                "from": "clientes",
                "localField": "id_cliente",
                "foreignField": "_id",
                "as": "cliente",
            }
        },
        {"$unwind": {"path": "$cliente", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "id_receta": "$_id",
                "medico": 1,
                "matricula_medico": 1,
                "fecha_emision": 1,
                "dispensas_autorizadas": 1,
                "dispensas_realizadas": 1,
                "proxima_dispensa": 1,
                "cliente": {
                    "$cond": [
                        {"$ifNull": ["$cliente", False]},
                        {
                            "id_cliente": "$cliente._id",
                            "nombre": "$cliente.nombre",
                            "apellido": "$cliente.apellido",
                            "dni": "$cliente.dni",
                            "email": "$cliente.email",
                            "telefono": "$cliente.telefono",
                            "obra_social": "$cliente.obra_social",
                            "nro_afiliado": "$cliente.nro_afiliado",
                            "activo": "$cliente.activo",
                        },
                        None,
                    ]
                },
            }
        },
        {"$sort": {"proxima_dispensa": 1, "id_receta": 1}},
    ]

    cursor = await db["recetas"].aggregate(pipeline)
    return await cursor.to_list()
