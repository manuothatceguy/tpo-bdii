import argparse

from .base import Columna, fecha, mostrar, pedir


def main() -> None:
    parser = argparse.ArgumentParser(description="Descontar stock de una venta registrada.")
    parser.add_argument("id_venta", help="ID de la venta, por ejemplo V016")
    args = parser.parse_args()

    respuesta = pedir("POST", f"/stock/ventas/{args.id_venta}/descuento")
    mostrar(
        f"Q15 - Lotes descontados para {respuesta['id_venta']} en {respuesta['id_sucursal']}",
        respuesta["lotes_descontados"],
        [
            Columna("Lote", "id_lote"),
            Columna("Nro. lote", "nro_lote"),
            Columna("Producto", "id_producto"),
            Columna("Vencimiento", "vencimiento", fecha),
            Columna("Descontado", "cantidad", alineacion="right"),
            Columna("Restante", "unidades_restantes", alineacion="right"),
        ],
    )


if __name__ == "__main__":
    main()
