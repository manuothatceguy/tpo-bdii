import argparse

from .base import Columna, fecha, mostrar, obtener, pesos


def detalle(evento: dict) -> str:
    datos = evento["datos"]
    if evento["tipo"] == "venta":
        return f"{datos['tipo']} · {datos['medio_pago']} · {pesos(datos['total'])} · {datos['estado']}"
    dispensas = f"{datos['dispensas_realizadas']}/{datos['dispensas_autorizadas']} dispensas"
    return f"{datos['medico']} · {datos['tipo']} · {dispensas} · {datos['estado']}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Historial de ventas y recetas de un cliente.")
    parser.add_argument("id_cliente", help="ID del cliente, por ejemplo C001")
    args = parser.parse_args()

    respuesta = obtener(f"/clientes/{args.id_cliente}/historial")
    mostrar(
        f"Q03 · Historial del cliente {respuesta['id_cliente']}",
        respuesta["historial"],
        [
            Columna("Fecha", "fecha", fecha),
            Columna("Tipo", "tipo", str.capitalize),
            Columna("ID", "datos._id"),
            Columna("Detalle", detalle),
        ],
    )


if __name__ == "__main__":
    main()
