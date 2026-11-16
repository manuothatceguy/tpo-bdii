from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, BeforeValidator, Field
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from ..dependencies.mongo import get_mongo_database
from ..dependencies.redis import get_redis
from ..servicios.errores import ErrorServicio
from ..servicios.ventas import registrar_venta

router = APIRouter(prefix="/ventas", tags=["Ventas"])

MedioPago = Literal["Efectivo", "Débito", "Crédito", "Transferencia", "Obra social"]


def _limpiar_texto(valor: object) -> object:
    return valor.strip() if isinstance(valor, str) else valor


TextoLimpio = Annotated[str, BeforeValidator(_limpiar_texto)]


class ItemVentaRequest(BaseModel):
    id_producto: TextoLimpio = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)


class RegistrarVentaRequest(BaseModel):
    id_cliente: TextoLimpio = Field(..., min_length=1)
    id_farmaceutico: TextoLimpio = Field(..., min_length=1)
    id_receta: TextoLimpio | None = Field(default=None, min_length=1)
    medio_pago: MedioPago
    items: list[ItemVentaRequest] = Field(..., min_length=1)


@router.get("/pendientes", summary="Q02 - Ventas pendientes con su farmacéutico")
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
        {"$unwind": {"path": "$farmaceutico", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "sucursales",
                "localField": "farmaceutico.id_sucursal",
                "foreignField": "_id",
                "as": "sucursal",
            }
        },
        {"$unwind": {"path": "$sucursal", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "id_venta": "$_id",
                "total": 1,
                "farmaceutico": {
                    "$cond": [
                        {"$ifNull": ["$farmaceutico", False]},
                        {
                            "nombre": "$farmaceutico.nombre",
                            "apellido": "$farmaceutico.apellido",
                            "matricula": "$farmaceutico.matricula",
                            "sucursal": "$sucursal.nombre",
                        },
                        None,
                    ]
                },
            }
        },
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return await cursor.to_list()


@router.get("/venta-libre", summary="Q09 - Ventas libres menores a $5.000")
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


@router.post("", status_code=status.HTTP_201_CREATED, summary="Q14 - Registrar venta")
async def registrar_nueva_venta(
    datos: RegistrarVentaRequest,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    """
    **Propósito:** Registrar una nueva venta 'Completada' con sus ítems.
    Valida que el cliente exista y esté activo, que el farmacéutico exista,
    esté activo y pertenezca a una sucursal de tipo 'Farmacia', que los
    productos existan y estén activos y, si hay productos bajo receta, que la
    receta exista, esté vigente y sea del mismo cliente. Calcula el total con
    los precios vigentes, descuenta el stock por FEFO en la sucursal del
    farmacéutico y actualiza la receta. Las escrituras en Redis y MongoDB se
    coordinan con una saga: si falla el registro en MongoDB, el stock
    descontado se devuelve.

    **Parámetros:** `datos`, cuerpo con el cliente, el farmacéutico, la receta
    (opcional), el medio de pago y los ítems (producto y cantidad). Los
    productos repetidos se suman en un solo ítem.

    **Valor de retorno:** Venta creada con su cabecera, ítems y total, junto
    con los lotes descontados y el ID del registro de saga.

    **Motor utilizado:** MongoDB y Redis.
    """
    try:
        resultado = await registrar_venta(
            db,
            redis,
            datos.id_cliente,
            datos.id_farmaceutico,
            datos.id_receta,
            datos.medio_pago,
            [(item.id_producto, item.cantidad) for item in datos.items],
        )
    except ErrorServicio as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except (PyMongoError, RedisError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible temporalmente",
        ) from error

    venta = dict(resultado["venta"])
    return {
        "venta": {"id_venta": venta.pop("_id"), **venta},
        "lotes_descontados": resultado["lotes_descontados"],
        "id_saga": resultado["id_saga"],
    }
