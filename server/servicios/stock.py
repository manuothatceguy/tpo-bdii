import json
from datetime import date, datetime, time, timezone

from redis.asyncio import Redis
from redis.exceptions import WatchError

from .errores import ReglaDeNegocio

MAX_INTENTOS = 3


class StockInsuficiente(ReglaDeNegocio):
    pass


class ConflictoDeStock(ReglaDeNegocio):
    pass


def clave_lote(id_lote: str) -> str:
    return f"lote:{id_lote}"


def clave_stock(id_sucursal: str, id_producto: str) -> str:
    return f"stock:{id_sucursal}:{id_producto}"


async def _ids_lotes_vigentes(lector, id_sucursal: str, id_producto: str) -> list[str]:
    hoy = datetime.combine(date.today(), time.min, tzinfo=timezone.utc).timestamp()
    return await lector.zrange(clave_stock(id_sucursal, id_producto), hoy, "+inf", byscore=True)


async def _leer_lotes(lector, ids_por_producto: dict[str, list[str]]) -> dict[str, list[dict]]:
    lotes = {}
    for id_producto, ids in ids_por_producto.items():
        lotes[id_producto] = []
        for id_lote in ids:
            unidades, vencimiento, nro_lote = await lector.hmget(
                clave_lote(id_lote), ["unidades", "vencimiento", "nro_lote"]
            )
            lotes[id_producto].append(
                {
                    "id_lote": id_lote,
                    "nro_lote": nro_lote,
                    "vencimiento": vencimiento,
                    "unidades": int(unidades or 0),
                }
            )
    return lotes


def _repartir_fefo(id_sucursal: str, cantidades: dict[str, int], lotes: dict[str, list[dict]]) -> list[dict]:
    plan = []
    for id_producto, cantidad in cantidades.items():
        disponible = sum(lote["unidades"] for lote in lotes[id_producto] if lote["unidades"] > 0)
        if disponible < cantidad:
            raise StockInsuficiente(
                f"Stock insuficiente para {id_producto} en {id_sucursal} "
                f"(pedido {cantidad}, vigente {disponible})"
            )
        pendiente = cantidad
        for lote in lotes[id_producto]:
            if pendiente == 0:
                break
            tomar = min(lote["unidades"], pendiente)
            if tomar <= 0:
                continue
            plan.append(
                {
                    "id_lote": lote["id_lote"],
                    "nro_lote": lote["nro_lote"],
                    "id_producto": id_producto,
                    "vencimiento": lote["vencimiento"],
                    "cantidad": tomar,
                    "unidades_restantes": lote["unidades"] - tomar,
                }
            )
            pendiente -= tomar
    return plan


async def planificar_descuento(redis: Redis, id_sucursal: str, cantidades: dict[str, int]) -> list[dict]:
    """
    **Propósito:** Calcular, sin modificar nada, qué lotes vigentes de la
    sucursal se usarían para cubrir las cantidades pedidas según FEFO.

    **Parámetros:** `redis`, cliente de Redis; `id_sucursal`, sucursal de los
    lotes; `cantidades`, unidades pedidas por ID de producto.

    **Valor de retorno:** Lista de lotes con la cantidad a descontar de cada
    uno. Lanza `StockInsuficiente` si algún producto no alcanza.

    **Motor utilizado:** Redis.
    """
    ids_por_producto = {
        id_producto: await _ids_lotes_vigentes(redis, id_sucursal, id_producto)
        for id_producto in cantidades
    }
    lotes = await _leer_lotes(redis, ids_por_producto)
    return _repartir_fefo(id_sucursal, cantidades, lotes)


async def descontar_stock(
    redis: Redis,
    id_sucursal: str,
    cantidades: dict[str, int],
    *,
    id_venta: str | None = None,
) -> list[dict]:
    """
    **Propósito:** Descontar las unidades pedidas de los lotes vigentes de la
    sucursal según FEFO, como una única operación atómica para todos los
    productos. Usa concurrencia optimista con `WATCH`, `MULTI` y `EXEC` y
    reintenta hasta `MAX_INTENTOS` veces si otro proceso modifica un lote.

    **Parámetros:** `redis`, cliente de Redis; `id_sucursal`, sucursal de los
    lotes; `cantidades`, unidades a descontar por ID de producto;
    `id_venta`, venta ya registrada en q15. Su resultado se guarda en la
    misma transacción que el descuento para evitar repetirlo.

    **Valor de retorno:** Lista de lotes descontados con la cantidad sacada de
    cada uno. Lanza `StockInsuficiente` sin tocar ningún lote si algún producto
    no alcanza, o `ConflictoDeStock` si se agotan los reintentos.

    **Motor utilizado:** Redis.
    """
    claves_stock = [clave_stock(id_sucursal, id_producto) for id_producto in cantidades]
    clave_descuento = f"saga:descuento:{id_venta}" if id_venta is not None else None
    for _ in range(MAX_INTENTOS):
        async with redis.pipeline(transaction=True) as pipe:
            if clave_descuento is not None:
                await pipe.watch(clave_descuento)
                resultado = await pipe.get(clave_descuento)
                if resultado is not None:
                    return json.loads(resultado)

            if claves_stock:
                await pipe.watch(*claves_stock)
            ids_por_producto = {
                id_producto: await _ids_lotes_vigentes(pipe, id_sucursal, id_producto)
                for id_producto in cantidades
            }
            claves_lotes = [clave_lote(id_lote) for ids in ids_por_producto.values() for id_lote in ids]
            if claves_lotes:
                await pipe.watch(*claves_lotes)
            lotes = await _leer_lotes(pipe, ids_por_producto)
            try:
                plan = _repartir_fefo(id_sucursal, cantidades, lotes)
            except StockInsuficiente:
                if clave_descuento is not None:
                    resultado = await pipe.get(clave_descuento)
                    if resultado is not None:
                        return json.loads(resultado)
                raise
            pipe.multi()
            for lote in plan:
                pipe.hincrby(clave_lote(lote["id_lote"]), "unidades", -lote["cantidad"])
            if clave_descuento is not None:
                pipe.set(clave_descuento, json.dumps(plan))
            try:
                await pipe.execute()
            except WatchError:
                continue
            return plan
    raise ConflictoDeStock(
        f"No se pudo descontar el stock en {id_sucursal} por cambios concurrentes, reintente la venta"
    )


async def devolver_stock(redis: Redis, lotes: list[dict]) -> None:
    """
    **Propósito:** Devolver a cada lote las unidades descontadas, sumando con
    `HINCRBY` en lugar de restaurar un valor anterior, para no pisar ventas
    concurrentes.

    **Parámetros:** `redis`, cliente de Redis; `lotes`, lista de lotes con su
    `id_lote` y la `cantidad` a devolver.

    **Valor de retorno:** Ninguno.

    **Motor utilizado:** Redis.
    """
    if not lotes:
        return
    async with redis.pipeline(transaction=True) as pipe:
        for lote in lotes:
            pipe.hincrby(clave_lote(lote["id_lote"]), "unidades", lote["cantidad"])
        await pipe.execute()
