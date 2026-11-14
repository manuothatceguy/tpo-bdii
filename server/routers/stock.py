from typing import Annotated

from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

from ..dependencies.mongo import get_mongo_database
from ..dependencies.redis import get_redis

router = APIRouter(prefix="/stock", tags=["Stock"])


@router.get("/lotes-bajos", summary="Q08 · Lotes con menos de 50 unidades")
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
    claves = [clave async for clave in redis.scan_iter(match="lote:*")]
    if not claves:
        return []

    pipeline = redis.pipeline()
    for clave in claves:
        pipeline.hgetall(clave)
    hashes = await pipeline.execute()

    lotes_bajos = []
    for clave, datos in zip(claves, hashes):
        if not datos:
            continue
        unidades = int(datos["unidades"])
        if unidades < 50:
            lotes_bajos.append(
                {
                    "id_lote": clave.removeprefix("lote:"),
                    "nro_lote": datos["nro_lote"],
                    "unidades": unidades,
                    "vencimiento": datos["vencimiento"],
                    "id_producto": datos["id_producto"],
                    "id_sucursal": datos["id_sucursal"],
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
            {"$unwind": "$proveedor"},
        ]
    )
    productos_por_id = {doc["_id"]: doc async for doc in productos_cursor}

    sucursales_cursor = db["sucursales"].find({"_id": {"$in": ids_sucursales}})
    sucursales_por_id = {doc["_id"]: doc async for doc in sucursales_cursor}

    resultado = []
    for lote in lotes_bajos:
        producto = productos_por_id.get(lote["id_producto"])
        sucursal = sucursales_por_id.get(lote["id_sucursal"])
        if producto is None or sucursal is None:
            continue
        proveedor = producto["proveedor"]

        resultado.append(
            {
                "id_lote": lote["id_lote"],
                "nro_lote": lote["nro_lote"],
                "unidades": lote["unidades"],
                "vencimiento": lote["vencimiento"],
                "producto": {
                    "id_producto": producto["_id"],
                    "nombre": producto["nombre"],
                    "principio_activo": producto["principio_activo"],
                    "categoria": producto["categoria"],
                    "presentacion": producto["presentacion"],
                    "condicion_venta": producto["condicion_venta"],
                    "precio_unit": producto["precio_unit"],
                    "activo": producto["activo"],
                },
                "sucursal": {
                    "id_sucursal": sucursal["_id"],
                    "nombre": sucursal["nombre"],
                    "tipo": sucursal["tipo"],
                    "direccion": sucursal["direccion"],
                    "ciudad": sucursal["ciudad"],
                    "provincia": sucursal["provincia"],
                    "telefono": sucursal["telefono"],
                    "activo": sucursal["activo"],
                },
                "proveedor": {
                    "id_proveedor": proveedor["_id"],
                    "razon_social": proveedor["razon_social"],
                    "cuit": proveedor["cuit"],
                    "tipo": proveedor["tipo"],
                    "ciudad": proveedor["ciudad"],
                    "provincia": proveedor["provincia"],
                    "telefono": proveedor["telefono"],
                    "activo": proveedor["activo"],
                },
            }
        )

    resultado.sort(key=lambda item: (item["unidades"], item["id_lote"]))
    return resultado
