from datetime import date, datetime, time, timedelta

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from redis.asyncio import Redis

from . import saga
from .errores import FalloRegistro, NoEncontrado, ReglaDeNegocio
from .stock import descontar_stock, planificar_descuento

CONDICIONES_CON_RECETA = ("Bajo receta", "Bajo receta archivada")
DIAS_ENTRE_DISPENSAS = 30
MAX_INTENTOS_ID = 3


def _siguiente_id(ids: list[str], prefijo: str, cantidad: int = 1) -> list[str]:
    max_num = 0
    for valor in ids:
        if isinstance(valor, str) and valor.startswith(prefijo) and valor[len(prefijo):].isdigit():
            max_num = max(max_num, int(valor[len(prefijo):]))
    return [f"{prefijo}{max_num + i:03d}" for i in range(1, cantidad + 1)]


async def _validar(db: AsyncDatabase, id_cliente: str, id_farmaceutico: str, id_receta: str | None, cantidades: dict[str, int]) -> tuple[dict, dict, dict | None]:
    cliente = await db["clientes"].find_one({"_id": id_cliente})
    if cliente is None:
        raise NoEncontrado(f"Cliente {id_cliente} no encontrado")
    if not cliente["activo"]:
        raise ReglaDeNegocio(f"El cliente {id_cliente} está dado de baja")

    farmaceutico = await db["farmaceuticos"].find_one({"_id": id_farmaceutico})
    if farmaceutico is None:
        raise NoEncontrado(f"Farmacéutico {id_farmaceutico} no encontrado")
    if not farmaceutico["activo"]:
        raise ReglaDeNegocio(f"El farmacéutico {id_farmaceutico} está dado de baja")
    sucursal = await db["sucursales"].find_one({"_id": farmaceutico["id_sucursal"]})
    if sucursal is None:
        raise NoEncontrado(f"Sucursal {farmaceutico['id_sucursal']} no encontrada")
    if not sucursal["activo"]:
        raise ReglaDeNegocio(f"La sucursal {sucursal['_id']} está dada de baja")
    if sucursal["tipo"] != "Farmacia":
        raise ReglaDeNegocio(
            f"El farmacéutico {id_farmaceutico} pertenece a {sucursal['_id']} ({sucursal['tipo']}), "
            "solo se registran ventas en sucursales de tipo Farmacia"
        )

    productos = {
        doc["_id"]: doc async for doc in db["productos"].find({"_id": {"$in": list(cantidades)}})
    }
    for id_producto in cantidades:
        producto = productos.get(id_producto)
        if producto is None:
            raise NoEncontrado(f"Producto {id_producto} no encontrado")
        if not producto["activo"]:
            raise ReglaDeNegocio(f"El producto {id_producto} está dado de baja")

    con_receta = [p for p in cantidades if productos[p]["condicion_venta"] in CONDICIONES_CON_RECETA]
    if id_receta is None:
        if con_receta:
            raise ReglaDeNegocio(f"El producto {con_receta[0]} se vende bajo receta y no se indicó una receta")
        return sucursal, productos, None

    if not con_receta:
        raise ReglaDeNegocio(
            f"La venta no incluye productos bajo receta, no corresponde indicar la receta {id_receta}"
        )
    receta = await db["recetas"].find_one({"_id": id_receta})
    if receta is None:
        raise NoEncontrado(f"Receta {id_receta} no encontrada")
    if receta["id_cliente"] != id_cliente:
        raise ReglaDeNegocio(f"La receta {id_receta} no pertenece al cliente {id_cliente}")
    if receta["estado"] != "Vigente":
        raise ReglaDeNegocio(f"La receta {id_receta} no está vigente (estado {receta['estado']})")
    if receta["dispensas_realizadas"] >= receta["dispensas_autorizadas"]:
        raise ReglaDeNegocio(f"La receta {id_receta} no tiene dispensas disponibles")
    return sucursal, productos, receta


def _cambios_receta(receta: dict, fecha: datetime) -> dict:
    realizadas = receta["dispensas_realizadas"] + 1
    if realizadas >= receta["dispensas_autorizadas"]:
        return {"dispensas_realizadas": realizadas, "estado": "Completada", "proxima_dispensa": None}
    return {
        "dispensas_realizadas": realizadas,
        "proxima_dispensa": fecha + timedelta(days=DIAS_ENTRE_DISPENSAS),
    }


async def registrar_en_mongo(db: AsyncDatabase, id_saga: ObjectId, cabecera: dict, cantidades: dict[str, int], productos: dict[str, dict], receta: dict | None) -> dict:
    """
    **Propósito:** Paso 2 de la saga. En una sola transacción de MongoDB
    inserta la venta con sus ítems, actualiza la receta y marca la saga como
    'Completado'. Los IDs de venta y de detalle se generan dentro de la
    transacción como el máximo actual más uno.

    **Parámetros:** `db`, base de MongoDB; `id_saga`, registro de saga;
    `cabecera`, datos de la venta sin ID ni ítems; `cantidades`, unidades por
    producto; `productos`, documentos de los productos; `receta`, receta a
    dispensar o `None`.

    **Valor de retorno:** Documento de la venta insertada.

    **Motor utilizado:** MongoDB.
    """

    async def transaccion(session) -> dict:
        ids_venta = [doc["_id"] async for doc in db["ventas"].find({}, {"_id": 1}, session=session)]
        cursor = await db["ventas"].aggregate(
            [{"$unwind": "$items"}, {"$project": {"_id": 0, "id": "$items.id_detalle"}}],
            session=session,
        )
        ids_detalle = [doc["id"] async for doc in cursor]

        id_venta = _siguiente_id(ids_venta, "V")[0]
        nuevos_detalles = _siguiente_id(ids_detalle, "D", len(cantidades))
        items = [
            {
                "id_detalle": id_detalle,
                "id_producto": id_producto,
                "cantidad": cantidad,
                "precio_unit": productos[id_producto]["precio_unit"],
            }
            for id_detalle, (id_producto, cantidad) in zip(nuevos_detalles, cantidades.items())
        ]
        venta = {
            "_id": id_venta,
            **cabecera,
            "total": sum(item["cantidad"] * item["precio_unit"] for item in items),
            "items": items,
        }

        if receta is not None:
            resultado = await db["recetas"].update_one(
                {
                    "_id": receta["_id"],
                    "estado": "Vigente",
                    "dispensas_realizadas": receta["dispensas_realizadas"],
                },
                {"$set": _cambios_receta(receta, cabecera["fecha"])},
                session=session,
            )
            if resultado.modified_count != 1:
                raise ReglaDeNegocio(f"La receta {receta['_id']} fue modificada por otra venta, reintente")

        await db["ventas"].insert_one(venta, session=session)

        if not await saga.marcar_completado(db, id_saga, id_venta, session):
            raise FalloRegistro("La saga ya no estaba en 'Redis descontado', la venta no se registró")
        return venta

    for intento in range(MAX_INTENTOS_ID):
        try:
            async with db.client.start_session() as session:
                return await session.with_transaction(transaccion)
        except DuplicateKeyError:
            if intento == MAX_INTENTOS_ID - 1:
                raise


async def registrar_venta(db: AsyncDatabase, redis: Redis, id_cliente: str, id_farmaceutico: str, id_receta: str | None, medio_pago: str, items: list[tuple[str, int]]) -> dict:
    """
    **Propósito:** Registrar una venta 'Completada' coordinando MongoDB y Redis
    con una saga. Valida todo contra MongoDB, verifica el stock vigente, crea
    el registro de saga, descuenta el stock en Redis (paso 1) y registra la
    venta y la receta en una transacción de MongoDB (paso 2). Si el paso 2
    falla, devuelve el stock descontado.

    **Parámetros:** `db`, base de MongoDB; `redis`, cliente de Redis;
    `id_cliente`, `id_farmaceutico` e `id_receta` (opcional) de la venta;
    `medio_pago`; `items`, pares de ID de producto y cantidad. Los productos
    repetidos se suman en un solo ítem.

    **Valor de retorno:** Diccionario con la venta creada, los lotes
    descontados y el ID de la saga.

    **Motor utilizado:** MongoDB y Redis.
    """
    cantidades: dict[str, int] = {}
    for id_producto, cantidad in items:
        cantidades[id_producto] = cantidades.get(id_producto, 0) + cantidad

    sucursal, productos, receta = await _validar(db, id_cliente, id_farmaceutico, id_receta, cantidades)
    id_sucursal = sucursal["_id"]

    plan = await planificar_descuento(redis, id_sucursal, cantidades)
    id_saga = await saga.crear_saga(db, id_sucursal, plan)

    try:
        lotes = await descontar_stock(redis, id_sucursal, cantidades)
    except ReglaDeNegocio as error:
        await saga.marcar_rechazado(db, id_saga, error.detail)
        raise
    await saga.marcar_redis_descontado(db, id_saga, lotes)

    cabecera = {
        "id_cliente": id_cliente,
        "id_farmaceutico": id_farmaceutico,
        "id_receta": id_receta,
        "fecha": datetime.combine(date.today(), time()),
        "tipo": "Venta libre" if receta is None else "Con receta",
        "medio_pago": medio_pago,
        "estado": "Completada",
        "id_sucursal": id_sucursal,
    }
    try:
        venta = await registrar_en_mongo(db, id_saga, cabecera, cantidades, productos, receta)
    except Exception as error:
        motivo = error.detail if isinstance(error, ReglaDeNegocio) else f"Falló el registro en MongoDB: {error}"
        await saga.compensar_saga(db, redis, id_saga, motivo)
        if isinstance(error, ReglaDeNegocio):
            raise
        raise FalloRegistro("No se pudo registrar la venta, el stock descontado fue devuelto") from error

    return {"venta": venta, "lotes_descontados": lotes, "id_saga": str(id_saga)}


async def descontar_stock_de_venta(db: AsyncDatabase, redis: Redis, id_venta: str) -> dict:
    """
    **Propósito:** Aplicar FEFO a los ítems de una venta completada ya
    registrada. Usa la sucursal guardada en la venta al momento del registro
    y omite lotes vencidos. Si un producto no alcanza, no modifica ningún
    lote. Si el descuento ya se aplicó mediante q14 o q15, devuelve ese
    resultado.

    **Parámetros:** `db`, base de MongoDB; `redis`, cliente de Redis;
    `id_venta`, identificador de la venta registrada.

    **Valor de retorno:** ID de venta, ID de sucursal y lotes descontados.

    **Motor utilizado:** MongoDB y Redis.
    """
    venta = await db["ventas"].find_one({"_id": id_venta})
    if venta is None:
        raise NoEncontrado(f"Venta {id_venta} no encontrada")
    if venta["estado"] != "Completada":
        raise ReglaDeNegocio(f"La venta {id_venta} no está completada")

    id_sucursal = venta["id_sucursal"]
    saga_completada = await db["sagas"].find_one(
        {"id_venta": id_venta, "estado": saga.COMPLETADO},
        {"lotes_descontados": 1},
    )
    if saga_completada is not None:
        lotes = saga_completada["lotes_descontados"]
    else:
        cantidades: dict[str, int] = {}
        for item in venta["items"]:
            id_producto = item["id_producto"]
            cantidad = item["cantidad"]
            if type(cantidad) is not int or cantidad <= 0:
                raise ReglaDeNegocio(f"Cantidad inválida para {id_producto} en la venta {id_venta}")
            cantidades[id_producto] = cantidades.get(id_producto, 0) + cantidad
        if not cantidades:
            raise ReglaDeNegocio(f"La venta {id_venta} no tiene ítems")
        lotes = await descontar_stock(redis, id_sucursal, cantidades, id_venta=id_venta)

    return {"id_venta": id_venta, "id_sucursal": id_sucursal, "lotes_descontados": lotes}
