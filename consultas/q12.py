from .base import Columna, mostrar, nombre_completo, obtener, si_no


def main() -> None:
    clientes = obtener("/clientes/sin-ventas")
    mostrar(
        "Q12 - Clientes sin ventas en el último año",
        clientes,
        [
            Columna("Cliente", "_id"),
            Columna("Nombre", nombre_completo),
            Columna("DNI", "dni"),
            Columna("Email", "email"),
            Columna("Teléfono", "telefono"),
            Columna("Ciudad", "ciudad"),
            Columna("Obra social", "obra_social"),
            Columna("Activo", "activo", si_no),
        ],
    )


if __name__ == "__main__":
    main()
