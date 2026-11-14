import argparse

from .base import Columna, consola, fecha, mostrar, pedir, pesos

MEDIOS_PAGO = ("Efectivo", "Débito", "Crédito", "Transferencia", "Obra social")


def item(valor: str) -> dict:
    id_producto, separador, cantidad = valor.partition(":")
    if not separador or not id_producto or not cantidad.isdigit():
        raise argparse.ArgumentTypeError(f"Ítem inválido '{valor}', use PRODUCTO:CANTIDAD (ej. PRD001:2)")
    return {"id_producto": id_producto, "cantidad": int(cantidad)}


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Registrar una nueva venta.")
    parser.add_argument("id_cliente", help="ID del cliente, por ejemplo C001")
    parser.add_argument("id_farmaceutico", help="ID del farmacéutico, por ejemplo F001")
    parser.add_argument("--medio-pago", required=True, choices=MEDIOS_PAGO)
    parser.add_argument("--item", dest="items", type=item, action="append", required=True, help="PRODUCTO:CANTIDAD, repetible")
    parser.add_argument("--receta", dest="id_receta", help="ID de la receta, por ejemplo RC002")
    return parser.parse_args()


def main() -> None:
    args = argumentos()
    respuesta = pedir("POST", "/ventas", vars(args))
    venta = respuesta["venta"]

    mostrar(
        "Q14 · Venta registrada",
        [venta],
        [
            Columna("Venta", "id_venta"),
            Columna("Fecha", "fecha", fecha),
            Columna("Cliente", "id_cliente"),
            Columna("Farmacéutico", "id_farmaceutico"),
            Columna("Sucursal", "id_sucursal"),
            Columna("Tipo", "tipo"),
            Columna("Receta", "id_receta"),
            Columna("Medio de pago", "medio_pago"),
            Columna("Total", "total", pesos, "right"),
            Columna("Estado", "estado"),
        ],
    )
    mostrar(
        f"Ítems de la venta {venta['id_venta']}",
        venta["items"],
        [
            Columna("Detalle", "id_detalle"),
            Columna("Producto", "id_producto"),
            Columna("Cantidad", "cantidad", alineacion="right"),
            Columna("Precio unit.", "precio_unit", pesos, "right"),
            Columna("Subtotal", lambda fila: fila["cantidad"] * fila["precio_unit"], pesos, "right"),
        ],
    )
    mostrar(
        "Lotes descontados (FEFO)",
        respuesta["lotes_descontados"],
        [
            Columna("Lote", "id_lote"),
            Columna("Nro. lote", "nro_lote"),
            Columna("Producto", "id_producto"),
            Columna("Vencimiento", "vencimiento", fecha),
            Columna("Descontado", "cantidad", alineacion="right"),
            Columna("Restante", "unidades_restantes", alineacion="right"),
        ],
    )
    consola.print(f"[dim]Saga {respuesta['id_saga']}[/]")


if __name__ == "__main__":
    main()
