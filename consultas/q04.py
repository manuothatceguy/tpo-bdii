from .base import Columna, mostrar, nombre_completo, obtener


def main() -> None:
    clientes = obtener("/clientes/varias-recetas")
    mostrar(
        "Q04 · Clientes con más de una receta",
        clientes,
        [
            Columna("Cliente", "id_cliente"),
            Columna("Nombre", nombre_completo),
            Columna("Recetas", "cantidad_recetas", alineacion="right"),
        ],
    )


if __name__ == "__main__":
    main()
