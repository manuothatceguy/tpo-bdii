from .base import Columna, fecha, mostrar, obtener, pesos


def items(venta: dict) -> str:
    return ", ".join(f"{item['id_producto']} x{item['cantidad']}" for item in venta["items"])


def main() -> None:
    ventas = obtener("/ventas/venta-libre")
    mostrar(
        "Q09 · Ventas libres menores a $ 5.000",
        ventas,
        [
            Columna("Venta", "id_venta"),
            Columna("Fecha", "fecha", fecha),
            Columna("Cliente", "id_cliente"),
            Columna("Farmacéutico", "id_farmaceutico"),
            Columna("Sucursal", "id_sucursal"),
            Columna("Medio de pago", "medio_pago"),
            Columna("Estado", "estado"),
            Columna("Ítems", items),
            Columna("Total", "total", pesos, "right"),
        ],
    )


if __name__ == "__main__":
    main()
