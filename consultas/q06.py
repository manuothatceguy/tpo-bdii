from .base import Columna, fecha, mostrar, nombre_completo, obtener


def main() -> None:
    recetas = obtener("/recetas/dispensas-vencidas")
    mostrar(
        "Q06 - Tratamientos prolongados con dispensa vencida",
        recetas,
        [
            Columna("Receta", "id_receta"),
            Columna("Próxima dispensa", "proxima_dispensa", fecha),
            Columna("Dispensas", lambda receta: f"{receta['dispensas_realizadas']}/{receta['dispensas_autorizadas']}", alineacion="right"),
            Columna("Médico", "medico"),
            Columna("Emisión", "fecha_emision", fecha),
            Columna("Cliente", "cliente.id_cliente"),
            Columna("Nombre", lambda receta: nombre_completo(receta["cliente"])),
            Columna("DNI", "cliente.dni"),
            Columna("Teléfono", "cliente.telefono"),
            Columna("Obra social", "cliente.obra_social"),
        ],
    )


if __name__ == "__main__":
    main()
