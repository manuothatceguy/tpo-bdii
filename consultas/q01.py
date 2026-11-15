from .base import Columna, mostrar, obtener, pesos


def main() -> None:
    productos = obtener("/productos/activos")
    mostrar(
        "Q01 - Productos activos con su proveedor",
        productos,
        [
            Columna("ID", "_id"),
            Columna("Producto", "nombre"),
            Columna("Principio activo", "principio_activo"),
            Columna("Categoría", "categoria"),
            Columna("Condición de venta", "condicion_venta"),
            Columna("Precio", "precio_unit", pesos, "right"),
            Columna("Proveedor", "proveedor.razon_social"),
            Columna("CUIT", "proveedor.cuit"),
            Columna("Tipo", "proveedor.tipo"),
            Columna("Ciudad", "proveedor.ciudad"),
            Columna("Teléfono", "proveedor.telefono"),
        ],
    )


if __name__ == "__main__":
    main()
