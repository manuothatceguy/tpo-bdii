from .base import Columna, mostrar, obtener


def main() -> None:
    productos = obtener("/productos/mas-vendidos")
    mostrar(
        "Q07 - Top 5 productos más vendidos",
        productos,
        [
            Columna("Producto", "id_producto"),
            Columna("Unidades vendidas", "unidades_vendidas", alineacion="right"),
        ],
    )


if __name__ == "__main__":
    main()
