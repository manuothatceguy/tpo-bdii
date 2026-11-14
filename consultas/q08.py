from .base import Columna, fecha, mostrar, obtener


def main() -> None:
    lotes = obtener("/stock/lotes-bajos")
    mostrar(
        "Q08 · Lotes con menos de 50 unidades",
        lotes,
        [
            Columna("Lote", "id_lote"),
            Columna("Nro. lote", "nro_lote"),
            Columna("Unidades", "unidades", alineacion="right"),
            Columna("Vencimiento", "vencimiento", fecha),
            Columna("Producto", "producto.nombre"),
            Columna("Sucursal", "sucursal.nombre"),
            Columna("Ciudad", "sucursal.ciudad"),
            Columna("Proveedor", "proveedor.razon_social"),
            Columna("Teléfono proveedor", "proveedor.telefono"),
        ],
    )


if __name__ == "__main__":
    main()
