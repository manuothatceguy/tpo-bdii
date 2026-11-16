from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, BeforeValidator, Field, model_validator
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from ..dependencies.mongo import get_mongo_database

router = APIRouter(prefix="/clientes", tags=["Clientes"])

ObraSocial = Literal[
    "OSDE",
    "Swiss Medical",
    "PAMI",
    "IOMA",
    "Galeno",
    "Sin cobertura",
]


def _limpiar_texto(valor: object) -> object:
    return valor.strip() if isinstance(valor, str) else valor


TextoLimpio = Annotated[str, BeforeValidator(_limpiar_texto)]


class AltaClienteRequest(BaseModel):
    id_cliente: TextoLimpio | None = Field(
        default=None,
        min_length=1,
        pattern=r"^[^\s/?#]+\z",
        description="Identificador único opcional (ej. C009). Si se omite, se autogenera.",
    )
    nombre: TextoLimpio = Field(..., min_length=1)
    apellido: TextoLimpio = Field(..., min_length=1)
    dni: TextoLimpio = Field(..., pattern=r"^[0-9]{7,8}\z", description="DNI numérico de 7 u 8 dígitos")
    email: TextoLimpio = Field(..., min_length=1)
    telefono: TextoLimpio = Field(..., min_length=1)
    ciudad: TextoLimpio = Field(..., min_length=1)
    provincia: TextoLimpio = Field(..., min_length=1)
    obra_social: ObraSocial
    nro_afiliado: TextoLimpio | None = None


class ModificarClienteRequest(BaseModel):
    email: TextoLimpio | None = Field(default=None, min_length=1)
    telefono: TextoLimpio | None = Field(default=None, min_length=1)
    ciudad: TextoLimpio | None = Field(default=None, min_length=1)
    provincia: TextoLimpio | None = Field(default=None, min_length=1)
    obra_social: ObraSocial | None = None
    nro_afiliado: TextoLimpio | None = None

    @model_validator(mode="after")
    def validar_campos_no_nulos(self) -> "ModificarClienteRequest":
        for campo in ("email", "telefono", "ciudad", "provincia", "obra_social"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo '{campo}' no puede ser nulo")
        return self


def formatear_cliente(doc: dict) -> dict:
    return {
        "id_cliente": doc["_id"],
        "nombre": doc["nombre"],
        "apellido": doc["apellido"],
        "dni": doc["dni"],
        "email": doc["email"],
        "telefono": doc["telefono"],
        "ciudad": doc["ciudad"],
        "provincia": doc["provincia"],
        "obra_social": doc["obra_social"],
        "nro_afiliado": doc["nro_afiliado"],
        "activo": doc["activo"],
    }


async def generar_id_cliente(db: AsyncDatabase) -> str:
    ids = [doc["_id"] async for doc in db["clientes"].find({}, {"_id": 1})]
    max_num = 0
    for cid in ids:
        if (
            isinstance(cid, str)
            and cid.startswith("C")
            and cid[1:].isascii()
            and cid[1:].isdigit()
        ):
            max_num = max(max_num, int(cid[1:]))
    return f"C{max_num + 1:03d}"


@router.get("/varias-recetas", summary="Q04 - Clientes con más de una receta")
async def clientes_con_varias_recetas(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar los clientes con más de una receta registrada,
    contando recetas de cualquier estado e incluyendo clientes inactivos.

    **Valor de retorno:** Lista de clientes con su ID, nombre, apellido y
    cantidad de recetas registradas.

    **Motor utilizado:** MongoDB.
    """
    pipeline = [
        {
            "$group": {
                "_id": "$id_cliente",
                "cantidad_recetas": {"$sum": 1},
            }
        },
        {"$match": {"cantidad_recetas": {"$gt": 1}}},
        {
            "$lookup": {
                "from": "clientes",
                "localField": "_id",
                "foreignField": "_id",
                "as": "cliente",
            }
        },
        {"$unwind": {"path": "$cliente", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 0,
                "id_cliente": "$_id",
                "nombre": {"$ifNull": ["$cliente.nombre", None]},
                "apellido": {"$ifNull": ["$cliente.apellido", None]},
                "cantidad_recetas": 1,
            }
        },
        {"$sort": {"cantidad_recetas": -1, "id_cliente": 1}},
    ]

    cursor = await db["recetas"].aggregate(pipeline)
    return await cursor.to_list()


@router.get("/sin-ventas", summary="Q12 - Clientes sin ventas en el último año")
async def clientes_sin_ventas_recientes(
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> list[dict]:
    """
    **Propósito:** Listar los clientes que no registran ventas en el último
    año.

    **Valor de retorno:** Lista de clientes sin ventas en el período, con todos
    sus datos.

    **Motor utilizado:** MongoDB.
    """
    hoy = datetime.now(timezone.utc).date()
    dia = min(hoy.day, monthrange(hoy.year - 1, hoy.month)[1])
    desde = datetime(hoy.year - 1, hoy.month, dia, tzinfo=timezone.utc)
    hasta = datetime.combine(hoy + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    pipeline = [
        {
            "$lookup": {
                "from": "ventas",
                "localField": "_id",
                "foreignField": "id_cliente",
                "pipeline": [
                    {
                        "$match": {
                            "fecha": {"$gte": desde, "$lt": hasta},
                            "estado": {"$ne": "Anulada"},
                        }
                    },
                    {"$limit": 1},
                ],
                "as": "ventas_del_periodo",
            }
        },
        {"$match": {"ventas_del_periodo": []}},
        {"$unset": "ventas_del_periodo"},
    ]

    cursor = await db["clientes"].aggregate(pipeline)
    return await cursor.to_list()


@router.get("/{id_cliente}/historial", summary="Q03 - Historial de un cliente")
async def historial_cliente(
    id_cliente: str,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> dict:
    """
    **Propósito:** Consultar el historial completo de ventas y recetas de un
    cliente, ordenado cronológicamente de más antiguo a más reciente.

    **Parámetros:** `id_cliente`, identificador del cliente a consultar.

    **Valor de retorno:** Diccionario con el ID del cliente y su historial de
    ventas y recetas ordenado por fecha. Cada evento incluye el tipo, la fecha
    y sus datos completos.

    **Motor utilizado:** MongoDB.
    """
    if await db["clientes"].find_one({"_id": id_cliente}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    pipeline = [
        {"$match": {"id_cliente": id_cliente}},
        {
            "$project": {
                "_id": 0,
                "tipo": {"$literal": "venta"},
                "fecha": "$fecha",
                "datos": "$$ROOT",
            }
        },
        {
            "$unionWith": {
                "coll": "recetas",
                "pipeline": [
                    {"$match": {"id_cliente": id_cliente}},
                    {
                        "$project": {
                            "_id": 0,
                            "tipo": {"$literal": "receta"},
                            "fecha": "$fecha_emision",
                            "datos": "$$ROOT",
                        }
                    },
                ],
            }
        },
        {"$sort": {"fecha": 1, "tipo": 1, "datos._id": 1}},
    ]

    cursor = await db["ventas"].aggregate(pipeline)
    return {"id_cliente": id_cliente, "historial": await cursor.to_list()}


@router.post("", status_code=status.HTTP_201_CREATED, summary="Q13 - Alta de cliente")
async def alta_cliente(
    datos: AltaClienteRequest,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> dict:
    """
    **Propósito:** Dar de alta un nuevo cliente validando que el DNI sea único
    y que los datos de cobertura sean consistentes.

    **Parámetros:** `datos`, cuerpo con los datos personales, de contacto y
    cobertura del nuevo cliente.

    **Valor de retorno:** Datos completos del cliente creado con `activo = True`.

    **Motor utilizado:** MongoDB.
    """
    dni = datos.dni
    if await db["clientes"].find_one({"dni": dni}, {"_id": 1}) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un cliente registrado con el DNI {dni}",
        )

    if datos.id_cliente is not None:
        id_cliente = datos.id_cliente
        if await db["clientes"].find_one({"_id": id_cliente}, {"_id": 1}) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un cliente con el ID {id_cliente}",
            )

    if datos.obra_social == "Sin cobertura":
        nro_afiliado = None
    else:
        if not datos.nro_afiliado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe indicar un número de afiliado cuando el cliente posee obra social",
            )
        nro_afiliado = datos.nro_afiliado

    if datos.id_cliente is not None:
        documento = {
            "_id": datos.id_cliente,
            "nombre": datos.nombre,
            "apellido": datos.apellido,
            "dni": dni,
            "email": datos.email,
            "telefono": datos.telefono,
            "ciudad": datos.ciudad,
            "provincia": datos.provincia,
            "obra_social": datos.obra_social,
            "nro_afiliado": nro_afiliado,
            "activo": True,
        }
        try:
            await db["clientes"].insert_one(documento)
        except DuplicateKeyError as exc:
            key_pattern = (exc.details or {}).get("keyPattern", {})
            if "dni" in key_pattern:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un cliente registrado con el DNI {dni}",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un cliente con el ID {datos.id_cliente}",
            ) from exc
        return formatear_cliente(documento)

    for _ in range(30):
        id_cliente = await generar_id_cliente(db)
        documento = {
            "_id": id_cliente,
            "nombre": datos.nombre,
            "apellido": datos.apellido,
            "dni": dni,
            "email": datos.email,
            "telefono": datos.telefono,
            "ciudad": datos.ciudad,
            "provincia": datos.provincia,
            "obra_social": datos.obra_social,
            "nro_afiliado": nro_afiliado,
            "activo": True,
        }
        try:
            await db["clientes"].insert_one(documento)
            return formatear_cliente(documento)
        except DuplicateKeyError as exc:
            key_pattern = (exc.details or {}).get("keyPattern", {})
            if "dni" in key_pattern:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un cliente registrado con el DNI {dni}",
                ) from exc

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No se pudo generar un identificador único para el cliente, intente nuevamente",
    )


@router.patch("/{id_cliente}", summary="Q13 - Modificación de cliente")
async def modificar_cliente(
    id_cliente: str,
    datos: ModificarClienteRequest,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> dict:
    """
    **Propósito:** Modificar los datos de contacto y/o cobertura de salud de un
    cliente existente.

    **Parámetros:** `id_cliente` en la ruta y `datos` con los campos de contacto
    o cobertura a actualizar.

    **Valor de retorno:** Datos completos del cliente actualizado.

    **Motor utilizado:** MongoDB.
    """
    for _ in range(5):
        actual = await db["clientes"].find_one({"_id": id_cliente})
        if actual is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )

        if not actual.get("activo", True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El cliente {id_cliente} está dado de baja",
            )

        cambios = datos.model_dump(exclude_unset=True)
        if not cambios:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe enviar al menos un campo para modificar",
            )

        nueva_obra_social = cambios.get("obra_social", actual["obra_social"])
        nuevo_nro_afiliado = (
            cambios["nro_afiliado"]
            if "nro_afiliado" in cambios
            else actual["nro_afiliado"]
        )

        if nueva_obra_social == "Sin cobertura":
            cambios["nro_afiliado"] = None
        else:
            if not nuevo_nro_afiliado:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debe indicar un número de afiliado cuando el cliente posee obra social",
                )
            cambios["nro_afiliado"] = nuevo_nro_afiliado

        actualizado = await db["clientes"].find_one_and_update(
            {
                "_id": id_cliente,
                "activo": True,
                "obra_social": actual["obra_social"],
                "nro_afiliado": actual["nro_afiliado"],
            },
            {"$set": cambios},
            return_document=ReturnDocument.AFTER,
        )
        if actualizado is not None:
            return formatear_cliente(actualizado)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Conflicto de concurrencia al modificar el cliente, intente nuevamente",
    )


@router.delete("/{id_cliente}", summary="Q13 - Baja lógica de cliente")
async def baja_cliente(
    id_cliente: str,
    db: Annotated[AsyncDatabase, Depends(get_mongo_database)],
) -> dict:
    """
    **Propósito:** Realizar la baja lógica de un cliente (`activo = False`),
    sin eliminar físicamente el registro de la base de datos.

    **Parámetros:** `id_cliente`, identificador del cliente a dar de baja.

    **Valor de retorno:** Datos completos del cliente con `activo = False`.

    **Motor utilizado:** MongoDB.
    """
    actualizado = await db["clientes"].find_one_and_update(
        {"_id": id_cliente, "activo": True},
        {"$set": {"activo": False}},
        return_document=ReturnDocument.AFTER,
    )
    if actualizado is None:
        actual = await db["clientes"].find_one({"_id": id_cliente}, {"_id": 1, "activo": 1})
        if actual is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente ya se encuentra dado de baja",
        )

    return formatear_cliente(actualizado)
