from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from ..dependencies.mongo import get_mongo_database

router = APIRouter()

ObraSocial = Literal[
    "OSDE",
    "Swiss Medical",
    "PAMI",
    "IOMA",
    "Galeno",
    "Sin cobertura",
]


class AltaClienteRequest(BaseModel):
    id_cliente: str | None = Field(
        default=None,
        description="Identificador único opcional (ej. C009). Si se omite, se autogenera.",
    )
    nombre: str = Field(..., min_length=1)
    apellido: str = Field(..., min_length=1)
    dni: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    ciudad: str = Field(..., min_length=1)
    provincia: str = Field(..., min_length=1)
    obra_social: ObraSocial
    nro_afiliado: str | None = None


class ModificarClienteRequest(BaseModel):
    email: str | None = Field(default=None, min_length=1)
    telefono: str | None = Field(default=None, min_length=1)
    ciudad: str | None = Field(default=None, min_length=1)
    provincia: str | None = Field(default=None, min_length=1)
    obra_social: ObraSocial | None = None
    nro_afiliado: str | None = None


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
        if isinstance(cid, str) and cid.startswith("C") and cid[1:].isdigit():
            max_num = max(max_num, int(cid[1:]))
    return f"C{max_num + 1:03d}"


@router.post("/q13", status_code=status.HTTP_201_CREATED)
async def q13_alta_cliente(
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
    dni = datos.dni.strip()
    if await db["clientes"].find_one({"dni": dni}, {"_id": 1}) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un cliente registrado con el DNI {dni}",
        )

    if datos.id_cliente is not None:
        id_cliente = datos.id_cliente.strip()
        if await db["clientes"].find_one({"_id": id_cliente}, {"_id": 1}) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un cliente con el ID {id_cliente}",
            )
    else:
        id_cliente = await generar_id_cliente(db)

    if datos.obra_social == "Sin cobertura":
        nro_afiliado = None
    else:
        if not datos.nro_afiliado or not datos.nro_afiliado.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe indicar un número de afiliado cuando el cliente posee obra social",
            )
        nro_afiliado = datos.nro_afiliado.strip()

    documento = {
        "_id": id_cliente,
        "nombre": datos.nombre.strip(),
        "apellido": datos.apellido.strip(),
        "dni": datos.dni.strip(),
        "email": datos.email.strip(),
        "telefono": datos.telefono.strip(),
        "ciudad": datos.ciudad.strip(),
        "provincia": datos.provincia.strip(),
        "obra_social": datos.obra_social,
        "nro_afiliado": nro_afiliado,
        "activo": True,
    }

    await db["clientes"].insert_one(documento)
    return formatear_cliente(documento)


@router.patch("/q13/{id_cliente}")
async def q13_modificar_cliente(
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
    actual = await db["clientes"].find_one({"_id": id_cliente})
    if actual is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
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
        if not nuevo_nro_afiliado or not nuevo_nro_afiliado.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe indicar un número de afiliado cuando el cliente posee obra social",
            )
        cambios["nro_afiliado"] = nuevo_nro_afiliado.strip()

    for campo in ("email", "telefono", "ciudad", "provincia"):
        if campo in cambios and cambios[campo] is not None:
            cambios[campo] = cambios[campo].strip()

    actualizado = await db["clientes"].find_one_and_update(
        {"_id": id_cliente},
        {"$set": cambios},
        return_document=ReturnDocument.AFTER,
    )
    return formatear_cliente(actualizado)


@router.delete("/q13/{id_cliente}")
async def q13_baja_cliente(
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
    actual = await db["clientes"].find_one({"_id": id_cliente})
    if actual is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )

    if not actual["activo"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente ya se encuentra dado de baja",
        )

    actualizado = await db["clientes"].find_one_and_update(
        {"_id": id_cliente},
        {"$set": {"activo": False}},
        return_document=ReturnDocument.AFTER,
    )
    return formatear_cliente(actualizado)
