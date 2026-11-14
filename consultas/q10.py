import argparse

from .base import Columna, mostrar, nombre_completo, obtener, si_no


def main() -> None:
    parser = argparse.ArgumentParser(description="Clientes atendidos en una sucursal.")
    parser.add_argument("id_sucursal", help="ID de la sucursal, por ejemplo S001")
    args = parser.parse_args()

    clientes = obtener(f"/sucursales/{args.id_sucursal}/clientes")
    mostrar(
        f"Q10 · Clientes atendidos en la sucursal {args.id_sucursal}",
        clientes,
        [
            Columna("Cliente", "id_cliente"),
            Columna("Nombre", nombre_completo),
            Columna("DNI", "dni"),
            Columna("Email", "email"),
            Columna("Teléfono", "telefono"),
            Columna("Obra social", "obra_social"),
            Columna("Activo", "activo", si_no),
            Columna("Ventas", "cantidad_ventas", alineacion="right"),
        ],
    )


if __name__ == "__main__":
    main()
