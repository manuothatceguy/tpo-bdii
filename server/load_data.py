import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient
from redis import Redis

from .dependencies.mongo import MONGO_DB, MONGO_URI
from .dependencies.redis import REDIS_URL

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ID_FIELDS = {
    "clientes": "id_cliente",
    "sucursales": "id_sucursal",
    "farmaceuticos": "id_farmaceutico",
    "proveedores": "id_proveedor",
    "productos": "id_producto",
    "recetas": "id_receta",
}
INT_FIELDS = {
    "unidades",
    "cantidad",
    "precio_unit",
    "total",
    "dispensas_autorizadas",
    "dispensas_realizadas",
}
DATE_FIELDS = {"fecha", "fecha_emision", "proxima_dispensa", "vencimiento"}
REDIS_PATTERNS = ("lote:*", "stock:*", "saga:*")


def parse_value(field: str, value: str):
    if value == "":
        return None
    if field in INT_FIELDS:
        return int(value)
    if field in DATE_FIELDS:
        return datetime.strptime(value, "%Y-%m-%d")
    if field == "activo":
        return value == "True"
    return value


def read_csv(name: str) -> list[dict]:
    filas = []
    for ruta in (DATA_DIR / f"{name}.csv", DATA_DIR / "adicionales" / f"{name}.csv"):
        if not ruta.exists():
            continue
        with ruta.open(encoding="utf-8", newline="") as file:
            filas.extend(
                {field: parse_value(field, value) for field, value in row.items()}
                for row in csv.DictReader(file)
            )
    return filas


def with_mongo_id(row: dict, id_field: str) -> dict:
    document = dict(row)
    document["_id"] = document.pop(id_field)
    return document


def build_ventas(sucursal_por_farmaceutico: dict[str, str]) -> list[dict]:
    items_por_venta = defaultdict(list)
    for detalle in read_csv("detalle_ventas"):
        id_venta = detalle.pop("id_venta")
        items_por_venta[id_venta].append(detalle)

    ventas = []
    for venta in read_csv("ventas"):
        documento = with_mongo_id(venta, "id_venta")
        documento["id_sucursal"] = sucursal_por_farmaceutico[venta["id_farmaceutico"]]
        documento["items"] = items_por_venta[venta["id_venta"]]
        ventas.append(documento)
    return ventas


def load_mongo(client: MongoClient) -> None:
    documentos = {
        coleccion: [with_mongo_id(row, id_field) for row in read_csv(coleccion)]
        for coleccion, id_field in ID_FIELDS.items()
    }
    documentos["ventas"] = build_ventas(
        {f["_id"]: f["id_sucursal"] for f in documentos["farmaceuticos"]}
    )

    db = client[MONGO_DB]
    db.drop_collection("sagas")
    for coleccion, filas in documentos.items():
        db.drop_collection(coleccion)
        db[coleccion].insert_many(filas)
        print(f"mongo {coleccion}: {len(filas)}")


def load_redis(client: Redis) -> None:
    lotes = read_csv("stock_lotes")
    claves_viejas = [
        clave for patron in REDIS_PATTERNS for clave in client.scan_iter(match=patron)
    ]

    pipeline = client.pipeline(transaction=True)
    if claves_viejas:
        pipeline.delete(*claves_viejas)
    for lote in lotes:
        vencimiento = lote["vencimiento"].replace(tzinfo=timezone.utc)
        pipeline.hset(
            f"lote:{lote['id_lote']}",
            mapping={
                "unidades": lote["unidades"],
                "vencimiento": vencimiento.date().isoformat(),
                "id_producto": lote["id_producto"],
                "id_sucursal": lote["id_sucursal"],
                "nro_lote": lote["nro_lote"],
            },
        )
        pipeline.zadd(
            f"stock:{lote['id_sucursal']}:{lote['id_producto']}",
            {lote["id_lote"]: vencimiento.timestamp()},
        )
    pipeline.execute()
    print(f"redis lotes: {len(lotes)}")


def main() -> None:
    with MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000) as mongo:
        load_mongo(mongo)
    with Redis.from_url(REDIS_URL, decode_responses=True) as redis_client:
        load_redis(redis_client)


if __name__ == "__main__":
    main()
