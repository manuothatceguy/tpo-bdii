from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from ..dependencies.mongo import get_mongo_database
from ..dependencies.redis import get_redis
from ..servicios.errores import ErrorServicio
from ..servicios.ventas import descontar_stock_de_venta

router = APIRouter(prefix="/stock", tags=["Stock"])


@router.get("/lotes-bajos", summary="Q08 - Lotes con menos de 50 unidades")
async def lotes_con_stock_bajo(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> list[dict]:
    """
    **Propósito:** Listar los lotes de stock que tienen menos de 50 unidades
    disponibles, junto con los datos de su producto, sucursal y proveedor.

    **Valor de retorno:** Lista de lotes ordenada de menor a mayor cantidad de
    unidades. Cada resultado incluye los datos del lote y objetos con la
    información del producto, la sucursal y el proveedor.

    **Motor utilizado:** Redis y MongoDB (combinación en la aplicación).
    """
    claves = list(dict.fromkeys([clave async for clave in redis.scan_iter(match="lote:*")]))
    if not claves:
        return []

    pipeline = redis.pipeline()
    for clave in claves:
        pipeline.hgetall(clave)
    hashes = await pipeline.execute()

    hoy_iso = datetime.now(timezone.utc).date().isoformat()
    lotes_bajos = []
    for clave, datos in zip(claves, hashes):
        if not datos:
            continue
        try:
            unidades = int(datos["unidades"])
            vencimiento = datos["vencimiento"]
            nro_lote = datos["nro_lote"]
            id_producto = datos["id_producto"]
            id_sucursal = datos["id_sucursal"]
        except (KeyError, TypeError, ValueError):
            continue
        if (
            not isinstance(vencimiento, str)
            or not vencimiento
            or nro_lote is None
            or id_producto is None
            or id_sucursal is None
        ):
            continue
        if 0 < unidades < 50 and vencimiento >= hoy_iso:
            lotes_bajos.append(
                {
                    "id_lote": clave.removeprefix("lote:"),
                    "nro_lote": nro_lote,
                    "unidades": unidades,
                    "vencimiento": vencimiento,
                    "id_producto": id_producto,
                    "id_sucursal": id_sucursal,
                }
            )

    if not lotes_bajos:
        return []

    ids_productos = list({lote["id_producto"] for lote in lotes_bajos})
    ids_sucursales = list({lote["id_sucursal"] for lote in lotes_bajos})

    productos_cursor = await db["productos"].aggregate(
        [
            {"$match": {"_id": {"$in": ids_productos}}},
            {
                "$lookup": {
                    "from": "proveedores",
                    "localField": "id_proveedor",
                    "foreignField": "_id",
                    "as": "proveedor",
                }
            },
            {"$unwind": {"path": "$proveedor", "preserveNullAndEmptyArrays": True}},
        ]
    )
    productos_por_id = {doc["_id"]: doc async for doc in productos_cursor}

    sucursales_cursor = db["sucursales"].find({"_id": {"$in": ids_sucursales}})
    sucursales_por_id = {doc["_id"]: doc async for doc in sucursales_cursor}

    resultado = []
    for lote in lotes_bajos:
        producto = productos_por_id.get(lote["id_producto"])
        if producto is not None and producto.get("activo") is False:
            continue
        sucursal = sucursales_por_id.get(lote["id_sucursal"])
        proveedor = producto.get("proveedor") if producto is not None else None

        resultado.append(
            {
                "id_lote": lote["id_lote"],
                "nro_lote": lote["nro_lote"],
                "unidades": lote["unidades"],
                "vencimiento": lote["vencimiento"],
                "producto": (
                    {
                        "id_producto": producto["_id"],
                        "nombre": producto["nombre"],
                        "principio_activo": producto["principio_activo"],
                        "categoria": producto["categoria"],
                        "presentacion": producto["presentacion"],
                        "condicion_venta": producto["condicion_venta"],
                        "precio_unit": producto["precio_unit"],
                        "activo": producto["activo"],
                    }
                    if producto is not None
                    else None
                ),
                "sucursal": (
                    {
                        "id_sucursal": sucursal["_id"],
                        "nombre": sucursal["nombre"],
                        "tipo": sucursal["tipo"],
                        "direccion": sucursal["direccion"],
                        "ciudad": sucursal["ciudad"],
                        "provincia": sucursal["provincia"],
                        "telefono": sucursal["telefono"],
                        "activo": sucursal["activo"],
                    }
                    if sucursal is not None
                    else None
                ),
                "proveedor": (
                    {
                        "id_proveedor": proveedor["_id"],
                        "razon_social": proveedor["razon_social"],
                        "cuit": proveedor["cuit"],
                        "tipo": proveedor["tipo"],
                        "ciudad": proveedor["ciudad"],
                        "provincia": proveedor["provincia"],
                        "telefono": proveedor["telefono"],
                        "activo": proveedor["activo"],
                    }
                    if proveedor is not None
                    else None
                ),
            }
        )

    resultado.sort(key=lambda item: (item["unidades"], item["id_lote"]))
    return resultado


@router.post("/ventas/{id_venta}/descuento", summary="Q15 - Descontar stock de una venta")
async def descontar_lotes_de_venta(
    id_venta: str,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    """
    **Propósito:** Descontar todos los ítems de una venta completada según
    FEFO, omitiendo lotes vencidos. Si falta stock vigente para algún ítem,
    rechaza la operación completa. Repetir la consulta devuelve el descuento
    existente.

    **Parámetros:** `id_venta`, identificador de la venta registrada.

    **Valor de retorno:** ID de venta, ID de sucursal y lotes descontados
    con las unidades consumidas y restantes.

    **Motor utilizado:** MongoDB y Redis.
    """
    try:
        return await descontar_stock_de_venta(db, redis, id_venta)
    except ErrorServicio as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except (PyMongoError, RedisError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible temporalmente",
        ) from error
