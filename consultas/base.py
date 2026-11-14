import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")

consola = Console()


@dataclass(frozen=True)
class Columna:
    encabezado: str
    campo: str | Callable[[dict], Any]
    formato: Callable[[Any], str] = str
    alineacion: str = "left"


def obtener(ruta: str) -> Any:
    return pedir("GET", ruta)


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None) -> Any:
    try:
        respuesta = httpx.request(metodo, f"{API_URL}{ruta}", json=cuerpo, timeout=10)
    except httpx.TransportError:
        consola.print(f"[bold red]No se pudo conectar con el servidor en {API_URL}.[/]")
        sys.exit(1)

    if respuesta.is_error:
        try:
            detalle = respuesta.json().get("detail", respuesta.text)
        except ValueError:
            detalle = respuesta.text
        if isinstance(detalle, list):
            detalle = "; ".join(f"{'.'.join(map(str, error['loc'][1:]))}: {error['msg']}" for error in detalle)
        consola.print(f"[bold red]Error {respuesta.status_code}:[/] {detalle}")
        sys.exit(1)

    return respuesta.json()


def mostrar(titulo: str, filas: list[dict], columnas: list[Columna]) -> None:
    if not filas:
        consola.print(f"[bold]{titulo}[/]\n[dim]Sin resultados.[/]")
        return

    tabla = Table(title=titulo, title_style="bold", header_style="bold cyan", min_width=len(titulo) + 4)
    for columna in columnas:
        tabla.add_column(columna.encabezado, justify=columna.alineacion)
    for fila in filas:
        tabla.add_row(*(_celda(fila, columna) for columna in columnas))

    consola.print(tabla)
    consola.print(f"[dim]{len(filas)} resultado(s).[/]")


def _celda(fila: dict, columna: Columna) -> str:
    if callable(columna.campo):
        valor = columna.campo(fila)
    else:
        valor = fila
        for clave in columna.campo.split("."):
            valor = valor.get(clave) if isinstance(valor, dict) else None
    return "-" if valor is None else columna.formato(valor)


def fecha(valor: str) -> str:
    return datetime.fromisoformat(valor).strftime("%d/%m/%Y")


def pesos(valor: int | float) -> str:
    return f"$ {valor:,.0f}".replace(",", ".")


def si_no(valor: bool) -> str:
    return "Sí" if valor else "No"


def nombre_completo(persona: dict) -> str:
    return f"{persona['nombre']} {persona['apellido']}"
