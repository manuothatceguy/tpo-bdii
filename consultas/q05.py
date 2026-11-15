from .base import Columna, mostrar, nombre_completo, obtener


def main() -> None:
    farmaceuticos = obtener("/farmaceuticos/ventas-recientes")
    mostrar(
        "Q05 - Ventas por farmacéutico en los últimos 60 días",
        farmaceuticos,
        [
            Columna("Farmacéutico", "id_farmaceutico"),
            Columna("Nombre", nombre_completo),
            Columna("Matrícula", "matricula"),
            Columna("Sucursal", "id_sucursal"),
            Columna("Ventas", "cantidad_ventas", alineacion="right"),
        ],
    )


if __name__ == "__main__":
    main()
