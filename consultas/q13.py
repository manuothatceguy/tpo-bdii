import argparse

from .base import Columna, mostrar, nombre_completo, pedir, si_no

COLUMNAS = [
    Columna("Cliente", "id_cliente"),
    Columna("Nombre", nombre_completo),
    Columna("DNI", "dni"),
    Columna("Email", "email"),
    Columna("Teléfono", "telefono"),
    Columna("Ciudad", "ciudad"),
    Columna("Provincia", "provincia"),
    Columna("Obra social", "obra_social"),
    Columna("Nro. afiliado", "nro_afiliado"),
    Columna("Activo", "activo", si_no),
]

CAMPOS_MODIFICABLES = ("email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado")


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ABM de clientes.")
    acciones = parser.add_subparsers(dest="accion", required=True)

    alta = acciones.add_parser("alta", help="Dar de alta un cliente")
    alta.add_argument("--id-cliente")
    for campo in ("nombre", "apellido", "dni", "email", "telefono", "ciudad", "provincia", "obra-social"):
        alta.add_argument(f"--{campo}", required=True)
    alta.add_argument("--nro-afiliado")

    modificar = acciones.add_parser("modificar", help="Modificar contacto y cobertura")
    modificar.add_argument("id_cliente")
    for campo in CAMPOS_MODIFICABLES:
        modificar.add_argument(f"--{campo.replace('_', '-')}")

    baja = acciones.add_parser("baja", help="Dar de baja lógica un cliente")
    baja.add_argument("id_cliente")

    return parser.parse_args()


def main() -> None:
    args = argumentos()
    datos = {campo: valor for campo, valor in vars(args).items() if campo != "accion" and valor is not None}

    if args.accion == "alta":
        cliente = pedir("POST", "/clientes", datos)
        titulo = "Q13 · Cliente dado de alta"
    elif args.accion == "modificar":
        cambios = {campo: datos[campo] for campo in CAMPOS_MODIFICABLES if campo in datos}
        cliente = pedir("PATCH", f"/clientes/{args.id_cliente}", cambios)
        titulo = "Q13 · Cliente modificado"
    else:
        cliente = pedir("DELETE", f"/clientes/{args.id_cliente}")
        titulo = "Q13 · Cliente dado de baja"

    mostrar(titulo, [cliente], COLUMNAS)


if __name__ == "__main__":
    main()
