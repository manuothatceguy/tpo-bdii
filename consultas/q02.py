from .base import Columna, mostrar, nombre_completo, obtener, pesos


def main() -> None:
    ventas = obtener("/ventas/pendientes")
    mostrar(
        "Q02 - Ventas pendientes con su farmacéutico",
        ventas,
        [
            Columna("Venta", "id_venta"),
            Columna("Total", "total", pesos, "right"),
            Columna("Farmacéutico", lambda venta: nombre_completo(venta.get("farmaceutico"))),
            Columna("Matrícula", "farmaceutico.matricula"),
            Columna("Sucursal", "farmaceutico.sucursal"),
        ],
    )


if __name__ == "__main__":
    main()
