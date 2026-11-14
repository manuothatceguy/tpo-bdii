# FarmaRed

Trabajo práctico obligatorio de Bases de Datos II (ITBA), grupo 8.

Backoffice de la red de farmacias FarmaRed sobre una arquitectura de persistencia políglota con MongoDB y Redis. Expone las consultas del enunciado como una API REST con FastAPI y trae un script de consola por consulta.

## Arquitectura

MongoDB guarda todas las entidades de negocio. Corre como replica set (`rs0`) porque las transacciones multi-documento no están disponibles en modo standalone. Redis guarda el stock por lote, con persistencia AOF, y resuelve la concurrencia del descuento con `WATCH`/`MULTI`/`EXEC`. Como una venta escribe en los dos motores sin una transacción común, el registro de una venta se coordina con una saga con compensación. La integridad referencial se valida en la aplicación contra MongoDB antes de escribir. La justificación completa está en el informe.

| Motor | Paradigma | Qué guarda |
| --- | --- | --- |
| MongoDB 7 (replica set) | Documentos | Clientes, sucursales, farmacéuticos, proveedores, productos, recetas, ventas con sus ítems embebidos y registros de saga |
| Redis 7 (AOF) | Clave-valor | Stock: un hash por lote (`lote:<id_lote>`) y un sorted set por sucursal y producto ordenado por vencimiento (`stock:<id_sucursal>:<id_producto>`) |

## Estructura del repositorio

```
.
├── .devcontainer/     # devcontainer.json y docker-compose.yml (app, api, mongo, redis)
├── data/              # CSV provistos por la cátedra
│   └── adicionales/   # registros adicionales del equipo
├── server/            # API FastAPI
│   ├── main.py
│   ├── load_data.py   # carga de datos en MongoDB y Redis
│   ├── dependencies/  # clientes de MongoDB y Redis
│   ├── routers/       # endpoints agrupados por entidad
│   └── servicios/     # lógica de negocio, descuento de stock y sagas
└── consultas/         # un script de consola por consulta (q01.py ... q15.py)
```

## Levantar el entorno

### GitHub Codespaces

1. En la página del repositorio, elegir **Code → Codespaces → Create codespace on main**.
2. Esperar a que termine la creación. El devcontainer levanta cuatro servicios:
   - `app`: contenedor de trabajo (Python 3.14).
   - `api`: ejecuta `fastapi dev` en el puerto 8000 y se reinicia solo ante cambios de código.
   - `mongo`: MongoDB 7 como replica set `rs0`, que se inicializa automáticamente en el healthcheck.
   - `redis`: Redis 7 con `appendonly yes`.
3. Al crearse el codespace, `postCreateCommand` instala `uv`, sincroniza las dependencias de `server/` y carga los datos (`python -m server.load_data`). No hace falta ningún paso manual.
4. La API queda disponible en el puerto 8000 (pestaña **Ports**). Desde la terminal del codespace se accede en `http://localhost:8000`.

### Local con VS Code Dev Containers

Requisitos: Docker y la extensión Dev Containers de VS Code.

1. Clonar el repositorio y abrirlo en VS Code.
2. Ejecutar **Dev Containers: Reopen in Container**.
3. El resto es igual que en Codespaces: se levantan los mismos servicios, se instalan las dependencias y se cargan los datos.

## Carga de datos

`server/load_data.py` lee los CSV de `data/` y, encima de ellos, los registros adicionales del equipo en `data/adicionales/`, que tienen las mismas columnas que los archivos provistos. Luego:

- En MongoDB borra y vuelve a crear cada colección (y vacía `sagas`). Los ítems de `detalle_ventas.csv` quedan embebidos en cada venta, junto con la sucursal del farmacéutico al momento de la venta.
- En Redis borra las claves `lote:*`, `stock:*` y `saga:*` y vuelve a cargar los lotes.

La carga es idempotente, se puede repetir en cualquier momento para volver al estado inicial. Desde la raíz del repositorio:

```sh
uv run --project server python -m server.load_data
```

## API

Con el entorno levantado, la documentación interactiva (Swagger) está en `http://localhost:8000/docs`.

| Consulta | Endpoint | Descripción |
| --- | --- | --- |
| Q01 | `GET /productos/activos` | Productos activos con su proveedor |
| Q02 | `GET /ventas/pendientes` | Ventas pendientes con su farmacéutico |
| Q03 | `GET /clientes/{id_cliente}/historial` | Historial de ventas y recetas de un cliente |
| Q04 | `GET /clientes/varias-recetas` | Clientes con más de una receta |
| Q05 | `GET /farmaceuticos/ventas-recientes` | Ventas por farmacéutico en los últimos 60 días |
| Q06 | `GET /recetas/dispensas-vencidas` | Tratamientos prolongados con dispensa vencida |
| Q07 | `GET /productos/mas-vendidos` | Top 5 productos más vendidos |
| Q08 | `GET /stock/lotes-bajos` | Lotes con menos de 50 unidades |
| Q09 | `GET /ventas/venta-libre` | Ventas libres menores a $5.000 |
| Q10 | `GET /sucursales/{id_sucursal}/clientes` | Clientes atendidos en una sucursal |
| Q11 | `GET /farmaceuticos/ingresos-mes` | Ingresos por farmacéutico en el mes actual |
| Q12 | `GET /clientes/sin-ventas` | Clientes sin ventas en el último año |
| Q13 | `POST /clientes`<br>`PATCH /clientes/{id_cliente}`<br>`DELETE /clientes/{id_cliente}` | Alta, modificación y baja lógica de clientes |
| Q14 | `POST /ventas` | Registro de una venta completada (cabecera e ítems), con descuento de stock en Redis coordinado por saga |
| Q15 | `POST /stock/ventas/{id_venta}/descuento` | Descuento atómico de stock por FEFO para una venta registrada |

Las consultas que dependen de la fecha ("últimos 60 días", "mes actual", "último año") usan la fecha del sistema.

## Ejecutar las consultas

Cada consulta tiene un script en `consultas/` que llama a la API y muestra el resultado como tabla. Se ejecutan desde la raíz del repositorio, con la API levantada:

```sh
uv run --project server python -m consultas.q01
uv run --project server python -m consultas.q02
uv run --project server python -m consultas.q04
uv run --project server python -m consultas.q05
uv run --project server python -m consultas.q06
uv run --project server python -m consultas.q07
uv run --project server python -m consultas.q08
uv run --project server python -m consultas.q09
uv run --project server python -m consultas.q11
uv run --project server python -m consultas.q12
```

Q03 y Q10 reciben un ID como argumento posicional:

```sh
uv run --project server python -m consultas.q03 C001   # historial del cliente C001
uv run --project server python -m consultas.q10 S001   # clientes de la sucursal S001
```

Q13 tiene tres subcomandos:

```sh
# Alta. --id-cliente y --nro-afiliado son opcionales. Si se omite el ID, la API asigna el siguiente.
uv run --project server python -m consultas.q13 alta --id-cliente C900 \
  --nombre Ana --apellido Pérez --dni 44123456 --email ana.perez@gmail.com \
  --telefono 1145556677 --ciudad Rosario --provincia "Santa Fe" \
  --obra-social OSDE --nro-afiliado OS-400123

# Modificación de contacto y cobertura. Se envían solo los campos indicados:
# --email, --telefono, --ciudad, --provincia, --obra-social, --nro-afiliado
uv run --project server python -m consultas.q13 modificar C900 --telefono 1149998877 --obra-social PAMI

# Baja lógica (activo = False)
uv run --project server python -m consultas.q13 baja C900
```

Las obras sociales válidas son `OSDE`, `Swiss Medical`, `PAMI`, `IOMA`, `Galeno` y `Sin cobertura`.

Q14 registra una venta. Recibe el cliente y el farmacéutico como argumentos posicionales, el medio de pago, uno o más ítems `producto:cantidad` y, si corresponde, la receta:

```sh
# Venta libre
uv run --project server python -m consultas.q14 C001 F001 --medio-pago Efectivo --item PRD001:2 --item PRD002:1

# Venta con receta
uv run --project server python -m consultas.q14 C007 F001 --medio-pago "Obra social" --item PRD003:1 --receta RC006
```

Antes de escribir, la API valida contra MongoDB el cliente, el farmacéutico, los productos y la receta. Después descuenta el stock en Redis y registra la venta en MongoDB. Si el segundo paso falla, la saga devuelve las unidades descontadas.

Las ventas modifican el stock y las recetas. Para volver al estado inicial, se vuelve a ejecutar `server.load_data`.

Q15 recibe el ID de una venta completada. Usa la sucursal registrada en la
venta y consume primero los lotes vigentes de vencimiento más próximo.
Si falta stock para algún producto, responde `409` y deja todos los lotes
intactos. Si q14 o un llamado anterior a q15 ya descontó la venta, devuelve
el resultado de ese descuento.

```sh
uv run --project server python -m consultas.q15 ID_VENTA
```

## Variables de entorno

Se leen del entorno o de un archivo `.env` en la raíz. El devcontainer ya define `MONGO_URI` y `REDIS_URL` para apuntar a los servicios de Docker Compose.

| Variable | Uso | Valor por defecto en el código | Valor en el devcontainer |
| --- | --- | --- | --- |
| `MONGO_URI` | Conexión a MongoDB | `mongodb://localhost:27017/?directConnection=true` | `mongodb://mongo:27017/?replicaSet=rs0` |
| `MONGO_DB` | Base de datos de MongoDB | `farmared` | `farmared` |
| `REDIS_URL` | Conexión a Redis | `redis://localhost:6379/0` | `redis://redis:6379` |
| `API_URL` | URL de la API que usan los scripts de `consultas/` | `http://localhost:8000` | `http://localhost:8000` |
