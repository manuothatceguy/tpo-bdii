from .base import Columna, mostrar, nombre_completo, obtener, pesos


def main() -> None:
    farmaceuticos = obtener("/farmaceuticos/ingresos-mes")
    mostrar(
        "Q11 - Ingresos por farmacéutico en el mes actual",
        farmaceuticos,
        [
            Columna("Farmacéutico", "id_farmaceutico"),
            Columna("Nombre", nombre_completo),
            Columna("Matrícula", "matricula"),
            Columna("Sucursal", "id_sucursal"),
            Columna("Ventas", "cantidad_ventas", alineacion="right"),
            Columna("Ingresos", "ingresos_totales", pesos, "right"),
        ],
    )


if __name__ == "__main__":
    main()
