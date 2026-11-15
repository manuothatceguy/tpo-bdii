window.Farma = (() => {
"use strict";

const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k === "style") n.style.cssText = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
};
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
};
const pick = (o, p) => p.split(".").reduce((a, k) => (a == null ? undefined : a[k]), o);
const nombre = r => `${r.nombre} ${r.apellido}`;
const enc = encodeURIComponent;
(() => {
  const css = document.createElement("style");
  css.textContent = ".fp-hint{width:100%;font-size:13px;line-height:1.45;padding:8px 12px;border-left:3px solid currentColor;opacity:.85;text-transform:none;letter-spacing:0;font-weight:400}.fp-run.fp-danger{background:#e5484d!important;border-color:#e5484d!important;color:#fff!important;box-shadow:none!important}";
  document.head.prepend(css);
})();

const FMT = {
  pesos: v => "$ " + Math.round(+v).toLocaleString("es-AR"),
  fecha: v => { const s = String(v).slice(0, 10).split("-"); return s.length === 3 ? `${s[2]}/${s[1]}/${s[0]}` : String(v); },
  sino: v => (v ? "Sí" : "No"),
  num: v => (+v).toLocaleString("es-AR"),
};
const CHIP = { Completada: "ok", Vigente: "info", Pendiente: "warn", Anulada: "bad" };

const CATS = {
  productos: { label: "Productos", color: "#38bdf8" },
  ventas: { label: "Ventas", color: "#34d399" },
  clientes: { label: "Clientes", color: "#a78bfa" },
  recetas: { label: "Recetas", color: "#f472b6" },
  farmaceuticos: { label: "Farmacéuticos", color: "#fbbf24" },
  sucursales: { label: "Sucursales", color: "#fb923c" },
  stock: { label: "Stock", color: "#2dd4bf" },
};

const OBRAS = ["OSDE", "Swiss Medical", "PAMI", "IOMA", "Galeno", "Sin cobertura"];
const MEDIOS = ["Efectivo", "Débito", "Crédito", "Transferencia", "Obra social"];
const MODIFICABLES = ["email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado"];
const ALTA = ["id_cliente", "nombre", "apellido", "dni", "email", "telefono", "ciudad", "provincia", "obra_social", "nro_afiliado"];
const ALTA_REQ = ["nombre", "apellido", "dni", "email", "telefono", "ciudad", "provincia", "obra_social"];

const COLS_CLIENTE = [["Cliente", "id_cliente"], ["Nombre", nombre], ["DNI", "dni"], ["Email", "email"], ["Teléfono", "telefono"], ["Ciudad", "ciudad"], ["Provincia", "provincia"], ["Obra social", "obra_social"], ["Nro. afiliado", "nro_afiliado"], ["Activo", "activo", "sino"]];
const COLS_LOTES = [["Lote", "id_lote"], ["Nro. lote", "nro_lote"], ["Producto", "id_producto"], ["Vencimiento", "vencimiento", "fecha"], ["Descontado", "cantidad", "num"], ["Restante", "unidades_restantes", "num"]];

const detalle03 = e => {
  const d = e.datos;
  if (e.tipo === "venta") return `${d.tipo} - ${d.medio_pago} - ${FMT.pesos(d.total)} - ${d.estado}`;
  return `${d.medico} - ${d.tipo} - ${d.dispensas_realizadas}/${d.dispensas_autorizadas} dispensas - ${d.estado}`;
};

const QUERIES = [
  { code: "Q01", cat: "productos", title: "Productos activos con su proveedor", short: "Productos activos", engine: "MongoDB", path: "/productos/activos",
    desc: "Catálogo de productos activos junto con los datos del proveedor que los abastece.",
    cols: [["ID", "_id"], ["Producto", "nombre"], ["Principio activo", "principio_activo"], ["Categoría", "categoria"], ["Condición de venta", "condicion_venta"], ["Precio", "precio_unit", "pesos"], ["Proveedor", "proveedor.razon_social"], ["CUIT", "proveedor.cuit"], ["Tipo", "proveedor.tipo"], ["Ciudad", "proveedor.ciudad"], ["Teléfono", "proveedor.telefono"]] },
  { code: "Q02", cat: "ventas", title: "Ventas pendientes con su farmacéutico", short: "Ventas pendientes", engine: "MongoDB", path: "/ventas/pendientes",
    desc: "Ventas en estado Pendiente con el total y el farmacéutico que las atendió.",
    cols: [["Venta", "id_venta"], ["Total", "total", "pesos"], ["Farmacéutico", r => nombre(r.farmaceutico)], ["Matrícula", "farmaceutico.matricula"], ["Sucursal", "farmaceutico.sucursal"]] },
  { code: "Q03", cat: "clientes", title: "Historial de ventas y recetas de un cliente", short: "Historial de cliente", engine: "MongoDB", path: "/clientes/{id_cliente}/historial",
    desc: "Línea de tiempo de las ventas y recetas de un cliente, ordenada por fecha.",
    fields: [{ name: "id_cliente", label: "Cliente", def: "C001", req: true, list: "dl-clientes" }],
    sections: r => [{ title: `Historial del cliente ${r.id_cliente}`, rows: r.historial, cols: [["Fecha", "fecha", "fecha"], ["Tipo", e => e.tipo[0].toUpperCase() + e.tipo.slice(1)], ["ID", "datos._id"], ["Detalle", detalle03]] }] },
  { code: "Q04", cat: "recetas", title: "Clientes con más de una receta", short: "Clientes con +1 receta", engine: "MongoDB", path: "/clientes/varias-recetas",
    desc: "Clientes que tienen más de una receta registrada.",
    cols: [["Cliente", "id_cliente"], ["Nombre", nombre], ["Recetas", "cantidad_recetas", "bar"]] },
  { code: "Q05", cat: "farmaceuticos", title: "Ventas por farmacéutico en los últimos 60 días", short: "Ventas últimos 60 días", engine: "MongoDB", path: "/farmaceuticos/ventas-recientes",
    desc: "Cantidad de ventas no anuladas de cada farmacéutico activo en los últimos 60 días.",
    cols: [["Farmacéutico", "id_farmaceutico"], ["Nombre", nombre], ["Matrícula", "matricula"], ["Sucursal", "id_sucursal"], ["Ventas", "cantidad_ventas", "bar"]] },
  { code: "Q06", cat: "recetas", title: "Tratamientos prolongados con dispensa vencida", short: "Dispensas vencidas", engine: "MongoDB", path: "/recetas/dispensas-vencidas",
    desc: "Recetas de tratamiento prolongado cuya próxima dispensa ya pasó.",
    cols: [["Receta", "id_receta"], ["Próxima dispensa", "proxima_dispensa", "fecha"], ["Dispensas", r => `${r.dispensas_realizadas}/${r.dispensas_autorizadas}`], ["Médico", "medico"], ["Emisión", "fecha_emision", "fecha"], ["Cliente", "cliente.id_cliente"], ["Nombre", r => nombre(r.cliente)], ["DNI", "cliente.dni"], ["Teléfono", "cliente.telefono"], ["Obra social", "cliente.obra_social"]] },
  { code: "Q07", cat: "productos", title: "Top 5 productos más vendidos", short: "Top 5 más vendidos", engine: "MongoDB", path: "/productos/mas-vendidos",
    desc: "Los cinco productos con más unidades vendidas en ventas completadas.",
    cols: [["Producto", "id_producto"], ["Unidades vendidas", "unidades_vendidas", "bar"]] },
  { code: "Q08", cat: "stock", title: "Lotes con menos de 50 unidades", short: "Lotes con stock bajo", engine: "Redis + MongoDB", path: "/stock/lotes-bajos",
    desc: "Lotes con menos de 50 unidades en Redis, con producto, sucursal y proveedor desde MongoDB.",
    cols: [["Lote", "id_lote"], ["Nro. lote", "nro_lote"], ["Unidades", "unidades", "bar"], ["Vencimiento", "vencimiento", "fecha"], ["Producto", "producto.nombre"], ["Sucursal", "sucursal.nombre"], ["Ciudad", "sucursal.ciudad"], ["Proveedor", "proveedor.razon_social"], ["Teléfono proveedor", "proveedor.telefono"]] },
  { code: "Q09", cat: "ventas", title: "Ventas libres menores a $ 5.000", short: "Ventas libres < $5.000", engine: "MongoDB", path: "/ventas/venta-libre",
    desc: "Ventas sin receta cuyo total es menor a $ 5.000.",
    cols: [["Venta", "id_venta"], ["Fecha", "fecha", "fecha"], ["Cliente", "id_cliente"], ["Farmacéutico", "id_farmaceutico"], ["Sucursal", "id_sucursal"], ["Medio de pago", "medio_pago"], ["Estado", "estado", "chip"], ["Ítems", v => v.items.map(i => `${i.id_producto} x${i.cantidad}`).join(", ")], ["Total", "total", "pesos"]] },
  { code: "Q10", cat: "sucursales", title: "Clientes atendidos en una sucursal", short: "Clientes por sucursal", engine: "MongoDB", path: "/sucursales/{id_sucursal}/clientes",
    desc: "Clientes que compraron en una sucursal y cuántas veces lo hicieron.",
    fields: [{ name: "id_sucursal", label: "Sucursal", def: "S001", req: true, list: "dl-sucursales" }],
    cols: [["Cliente", "id_cliente"], ["Nombre", nombre], ["DNI", "dni"], ["Email", "email"], ["Teléfono", "telefono"], ["Obra social", "obra_social"], ["Activo", "activo", "sino"], ["Ventas", "cantidad_ventas", "bar"]] },
  { code: "Q11", cat: "farmaceuticos", title: "Ingresos por farmacéutico en el mes actual", short: "Ingresos del mes", engine: "MongoDB", path: "/farmaceuticos/ingresos-mes",
    desc: "Ventas e ingresos totales de cada farmacéutico en el mes calendario actual.",
    cols: [["Farmacéutico", "id_farmaceutico"], ["Nombre", nombre], ["Matrícula", "matricula"], ["Sucursal", "id_sucursal"], ["Ventas", "cantidad_ventas", "num"], ["Ingresos", "ingresos_totales", "bar", "pesos"]] },
  { code: "Q12", cat: "clientes", title: "Clientes sin ventas en el último año", short: "Clientes sin ventas", engine: "MongoDB", path: "/clientes/sin-ventas",
    desc: "Clientes que no registran ventas en los últimos doce meses.",
    cols: [["Cliente", "_id"], ["Nombre", nombre], ["DNI", "dni"], ["Email", "email"], ["Teléfono", "telefono"], ["Ciudad", "ciudad"], ["Obra social", "obra_social"], ["Activo", "activo", "sino"]] },
  { code: "Q13", cat: "clientes", title: "Alta, modificación y baja de clientes", short: "ABM de clientes", engine: "MongoDB", method: "POST · PATCH · DELETE", path: "/clientes",
    desc: "Alta de clientes nuevos, cambio de contacto y cobertura, y baja lógica.", mutation: true,
    modes: ["Alta", "Modificar", "Baja"],
    modeInfo: {
      Alta: "Crea un cliente nuevo con activo = true. Si dejás vacío el ID, la API asigna el siguiente libre.",
      Modificar: "Cambia solo contacto y cobertura del cliente. Los campos que dejes vacíos no se modifican.",
      Baja: "Baja lógica: el cliente no se borra de MongoDB. Se marca activo = false y conserva todo su historial de ventas y recetas. Desde ese momento no puede registrar compras nuevas (Q14 lo rechaza). Si ya estaba dado de baja, la API responde 400.",
    },
    modeRun: { Alta: "Dar de alta", Modificar: "Guardar cambios", Baja: "Dar de baja" },
    confirmMode: "Baja",
    fields: [
      { name: "id_cliente", label: "ID cliente", ph: "C900", modes: ["Alta", "Modificar", "Baja"], list: "dl-clientes" },
      { name: "nombre", label: "Nombre", modes: ["Alta"] },
      { name: "apellido", label: "Apellido", modes: ["Alta"] },
      { name: "dni", label: "DNI", modes: ["Alta"] },
      { name: "email", label: "Email", modes: ["Alta", "Modificar"] },
      { name: "telefono", label: "Teléfono", modes: ["Alta", "Modificar"] },
      { name: "ciudad", label: "Ciudad", modes: ["Alta", "Modificar"] },
      { name: "provincia", label: "Provincia", modes: ["Alta", "Modificar"] },
      { name: "obra_social", label: "Obra social", type: "select", options: ["", ...OBRAS], modes: ["Alta", "Modificar"] },
      { name: "nro_afiliado", label: "Nro. afiliado", modes: ["Alta", "Modificar"] },
    ],
    request(v, strict) {
      const need = (ok, msg) => { if (!ok && strict) throw new Error(msg); };
      const take = keys => Object.fromEntries(keys.filter(k => v[k]).map(k => [k, v[k]]));
      if (v.modo === "Alta") {
        for (const k of ALTA_REQ) need(v[k], `Para el alta completá "${this.fields.find(f => f.name === k).label}".`);
        need(/^\d{7,8}$/.test(v.dni), "El DNI debe tener 7 u 8 dígitos numéricos.");
        return { method: "POST", path: "/clientes", body: take(ALTA) };
      }
      need(v.id_cliente, "Indicá el ID del cliente.");
      const path = `/clientes/${enc(v.id_cliente || "{id_cliente}")}`;
      if (v.modo === "Modificar") {
        const body = take(MODIFICABLES);
        need(Object.keys(body).length, "Indicá al menos un campo a modificar.");
        return { method: "PATCH", path, body };
      }
      return { method: "DELETE", path };
    },
    sections(r, req) {
      const t = { POST: "Cliente dado de alta", PATCH: "Cliente modificado", DELETE: "Cliente dado de baja" }[req.method];
      return [{ title: t, rows: [r], cols: COLS_CLIENTE }];
    },
    toast: (r, req) => `${r.id_cliente}: ${{ POST: "alta registrada", PATCH: "datos actualizados", DELETE: "baja lógica aplicada" }[req.method]}` },
  { code: "Q14", cat: "ventas", title: "Registrar una venta", short: "Registrar venta", engine: "MongoDB + Redis (saga)", method: "POST", path: "/ventas",
    desc: "Registra la venta, descuenta stock por FEFO en Redis y lo coordina con una saga con compensación.", mutation: true,
    fields: [
      { name: "id_cliente", label: "Cliente", def: "C001", list: "dl-clientes" },
      { name: "id_farmaceutico", label: "Farmacéutico", def: "F001", list: "dl-farmaceuticos" },
      { name: "medio_pago", label: "Medio de pago", type: "select", options: MEDIOS },
      { name: "id_receta", label: "Receta (opcional)", ph: "RC006", list: "dl-recetas" },
      { name: "items", label: "Ítems", type: "items" },
    ],
    request(v, strict) {
      const need = (ok, msg) => { if (!ok && strict) throw new Error(msg); };
      need(v.id_cliente, "Indicá el cliente.");
      need(v.id_farmaceutico, "Indicá el farmacéutico.");
      need(v.items.length, "Agregá al menos un ítem.");
      need(v.items.every(i => i.cantidad > 0), "Las cantidades tienen que ser mayores a cero.");
      const body = { id_cliente: v.id_cliente, id_farmaceutico: v.id_farmaceutico, medio_pago: v.medio_pago, items: v.items };
      if (v.id_receta) body.id_receta = v.id_receta;
      return { method: "POST", path: "/ventas", body };
    },
    sections: r => [
      { title: "Venta registrada", rows: [r.venta], cols: [["Venta", "id_venta"], ["Fecha", "fecha", "fecha"], ["Cliente", "id_cliente"], ["Farmacéutico", "id_farmaceutico"], ["Sucursal", "id_sucursal"], ["Tipo", "tipo"], ["Receta", "id_receta"], ["Medio de pago", "medio_pago"], ["Total", "total", "pesos"], ["Estado", "estado", "chip"]] },
      { title: `Ítems de la venta ${r.venta.id_venta}`, rows: r.venta.items, cols: [["Detalle", "id_detalle"], ["Producto", "id_producto"], ["Cantidad", "cantidad", "num"], ["Precio unit.", "precio_unit", "pesos"], ["Subtotal", f => f.cantidad * f.precio_unit, "pesos"]] },
      { title: "Lotes descontados (FEFO)", rows: r.lotes_descontados, cols: COLS_LOTES },
    ],
    note: r => `Saga ${r.id_saga}`,
    toast: r => `Venta ${r.venta.id_venta} registrada por ${FMT.pesos(r.venta.total)}` },
  { code: "Q15", cat: "stock", title: "Descuento de stock por venta (FEFO)", short: "Descontar stock", engine: "Redis (WATCH/MULTI)", method: "POST", path: "/stock/ventas/{id_venta}/descuento",
    desc: "Descuenta de forma atómica el stock de una venta, consumiendo primero los lotes que vencen antes.", mutation: true,
    fields: [{ name: "id_venta", label: "Venta", def: "V016", ph: "V016", req: true, list: "dl-ventas" }],
    sections: r => [{ title: `Lotes descontados para ${r.id_venta} en ${r.id_sucursal}`, rows: r.lotes_descontados, cols: COLS_LOTES }],
    toast: r => `Stock descontado para ${r.id_venta}` },
];
QUERIES.forEach(q => { q.color = CATS[q.cat].color; q.method = q.method || "GET"; });
const byCode = code => QUERIES.find(q => q.code === code);

const STATIONS = [
  { id: "caja", title: "Mostrador y caja", sub: "Ventas, saga y FEFO", color: "#34d399", queries: ["Q14", "Q15", "Q02", "Q09"] },
  { id: "estanteria", title: "Góndolas y depósito", sub: "Productos y lotes en Redis", color: "#38bdf8", queries: ["Q01", "Q08"] },
  { id: "recetas", title: "Terminal de recetas", sub: "Recetas y dispensas", color: "#f472b6", queries: ["Q06", "Q04"] },
  { id: "clientes", title: "Atención al cliente", sub: "Padrón, historial y ABM", color: "#a78bfa", queries: ["Q13", "Q03", "Q10", "Q12"] },
  { id: "gerencia", title: "Gerencia", sub: "Rankings e ingresos", color: "#fbbf24", queries: ["Q07", "Q11", "Q05"] },
];

const THEMES = [
  { id: "farmaxp", name: "FarmaXP", href: "../" },
  { id: "ps2", name: "PS2", href: "ps2.html" },
  { id: "farmatwin", name: "FarmaTwin 3D", href: "farmatwin.html" },
  { id: "farmacraft", name: "FarmaCraft", href: "farmacraft.html" },
  { id: "farmaoflegends", name: "Farma of Legends", href: "farmaoflegends.html" },
  { id: "farmanite", name: "FarmaNite", href: "farmanite.html" },
  { id: "grandthefarma", name: "Grand Theft Farma", href: "grandthefarma.html" },
  { id: "farmatown", name: "FarmaTown", href: "farmatown.html" },
  { id: "farmahitrun", name: "Farma Hit & Run", href: "farmahitrun.html" },
  { id: "farmacampus", name: "FarmaCampus", href: "farmacampus.html" },
  { id: "farmaturro", name: "Mundo FarmaTurro", href: "farmaturro.html" },
];

const API = {
  base: store.get("farmared.api") || (location.protocol.startsWith("http") ? location.origin : "http://localhost:8000"),
};

async function call(method, path, body) {
  const t0 = performance.now();
  let res;
  try {
    res = await fetch(API.base + path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  } catch {
    const e = new Error(`No se pudo conectar con la API en ${API.base}. Revisá que esté levantada y que abriste la página desde la API (por ejemplo http://localhost:8000/temas/).`);
    e.status = 0;
    throw e;
  }
  const ms = Math.round(performance.now() - t0);
  const txt = await res.text();
  let data;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = txt; }
  if (!res.ok) {
    let d = data && typeof data === "object" && "detail" in data ? data.detail : txt;
    if (Array.isArray(d)) d = d.map(x => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join("\n");
    const e = new Error(typeof d === "string" ? d : JSON.stringify(d));
    e.status = res.status;
    e.ms = ms;
    throw e;
  }
  return { data, status: res.status, ms };
}

const get = async path => (await call("GET", path)).data;

async function ping() {
  try { return (await fetch(API.base + "/openapi.json", { cache: "no-store" })).ok; } catch { return false; }
}

async function snapshot() {
  const safe = p => get(p).catch(() => null);
  const [productos, lotes, pendientes, ingresos, top, f60, sinVentas, variasRecetas] = await Promise.all([
    safe("/productos/activos"), safe("/stock/lotes-bajos"), safe("/ventas/pendientes"), safe("/farmaceuticos/ingresos-mes"), safe("/productos/mas-vendidos"),
    safe("/farmaceuticos/ventas-recientes"), safe("/clientes/sin-ventas"), safe("/clientes/varias-recetas"),
  ]);
  const setDl = (id, opts) => {
    const dl = document.getElementById(id) || document.body.appendChild(el("datalist", { id }));
    dl.replaceChildren(...opts.map(([v, l]) => el("option", { value: v, label: l })));
  };
  if (productos) setDl("dl-productos", productos.map(p => [p._id, `${p.nombre} (${p.condicion_venta})`]));
  if (f60) setDl("dl-farmaceuticos", f60.map(f => [f.id_farmaceutico, `${nombre(f)} · ${f.id_sucursal}`]));
  const cliMap = new Map();
  for (let i = 1; i <= 18; i++) cliMap.set(`C${String(i).padStart(3, "0")}`, `Cliente C${String(i).padStart(3, "0")}`);
  for (const c of variasRecetas || []) cliMap.set(c.id_cliente, `${nombre(c)} (${c.cantidad_recetas} recetas)`);
  for (const c of sinVentas || []) cliMap.set(c._id, `${nombre(c)}${c.activo === false ? " · inactivo" : ""}`);
  setDl("dl-clientes", [...cliMap.entries()]);
  setDl("dl-sucursales", Array.from({ length: 14 }, (_, i) => { const s = `S${String(i + 1).padStart(3, "0")}`; return [s, `Sucursal ${s}`]; }));
  setDl("dl-ventas", ["V016", "V003", "V004", "V005", "V008", "V009", "V013", "V019", "V021", "V026", "V027", "V028", "V032"].map(v => [v, `Venta completada ${v}`]));
  setDl("dl-recetas", Array.from({ length: 18 }, (_, i) => { const r = `RC${String(i + 1).padStart(3, "0")}`; return [r, `Receta ${r}`]; }));
  return {
    online: productos != null,
    productos: productos || [],
    lotes: lotes || [],
    pendientes: pendientes || [],
    ingresos: ingresos || [],
    top: top || [],
    totalIngresos: (ingresos || []).reduce((s, f) => s + f.ingresos_totales, 0),
  };
}

const Sound = {
  ctx: null,
  muted: store.get("farmared.mute") === "1",
  get() {
    if (this.muted) return null;
    if (!this.ctx && navigator.userActivation && !navigator.userActivation.hasBeenActive) return null;
    if (!this.ctx) { try { this.ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch { return null; } }
    if (this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  },
  tone(f, delay = 0, dur = .2, type = "sine", vol = .06, slide) {
    const a = this.get(); if (!a) return;
    const t = a.currentTime + delay, o = a.createOscillator(), g = a.createGain();
    o.type = type;
    o.frequency.setValueAtTime(f, t);
    if (slide) o.frequency.exponentialRampToValueAtTime(slide, t + dur);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vol, t + Math.min(.03, dur / 4));
    g.gain.exponentialRampToValueAtTime(.0001, t + dur);
    o.connect(g).connect(a.destination);
    o.start(t);
    o.stop(t + dur + .05);
  },
  noise(delay = 0, dur = .3, vol = .08, freq = 1200) {
    const a = this.get(); if (!a) return;
    const t = a.currentTime + delay, len = Math.ceil(a.sampleRate * dur), buf = a.createBuffer(1, len, a.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const s = a.createBufferSource(), f = a.createBiquadFilter(), g = a.createGain();
    s.buffer = buf; f.type = "bandpass"; f.frequency.value = freq; g.gain.value = vol;
    s.connect(f).connect(g).connect(a.destination);
    s.start(t);
  },
  toggle() { this.muted = !this.muted; store.set("farmared.mute", this.muted ? "1" : "0"); return this.muted; },
};

function cmp(a, b) {
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), "es", { numeric: true });
}

function cell(v, c, max) {
  const td = el("td", { class: c.right ? "fp-r" : null });
  if (v == null || v === "") { td.textContent = "-"; return td; }
  if (c.fmt === "bar") {
    td.append(el("div", { class: "fp-barcell" },
      el("span", { text: c.sub ? FMT[c.sub](v) : FMT.num(v) }),
      el("div", { class: "fp-track" }, el("i", { style: `width:${Math.max(2, (+v / max) * 100)}%` }))));
    return td;
  }
  if (c.fmt === "chip") { td.append(el("span", { class: `fp-chip fp-${CHIP[v] || "info"}`, text: v })); return td; }
  td.textContent = FMT[c.fmt] ? FMT[c.fmt](v) : String(v);
  return td;
}

function table(rows, cols) {
  const spec = cols.map(([h, f, fmt, sub]) => ({ h, f, fmt, sub, right: ["pesos", "num", "bar"].includes(fmt) }));
  const val = (r, c) => (typeof c.f === "function" ? c.f(r) : pick(r, c.f));
  const max = spec.map(c => (c.fmt === "bar" ? Math.max(1, ...rows.map(r => +val(r, c) || 0)) : 0));
  let data = rows.slice(), sortI = -1, dir = 1;
  const tbody = el("tbody");
  const ths = spec.map((c, i) => el("th", { class: c.right ? "fp-r" : null, text: c.h, onclick: () => {
    dir = sortI === i ? -dir : 1;
    sortI = i;
    data.sort((a, b) => cmp(val(a, c), val(b, c)) * dir);
    ths.forEach((t, j) => (j === i ? t.setAttribute("data-s", dir > 0 ? "▲" : "▼") : t.removeAttribute("data-s")));
    paint(false);
  } }));
  const paint = animate => {
    tbody.replaceChildren(...data.map((r, k) => {
      const tr = el("tr", {}, spec.map((c, i) => cell(val(r, c), c, max[i])));
      if (animate) tr.style.animationDelay = `${Math.min(k, 25) * 28}ms`;
      else tr.style.animation = "none";
      return tr;
    }));
  };
  paint(true);
  return el("div", { class: "fp-tablewrap" }, el("table", { class: "fp-table" }, el("thead", {}, el("tr", {}, ths)), tbody));
}

function itemsEditor(initial) {
  const list = el("div", { class: "fp-items" });
  const add = (p = "", c = 1) => {
    const row = el("div", { class: "fp-item" },
      el("input", { class: "fp-ip", placeholder: "PRD001", value: p, list: "dl-productos" }),
      el("span", { text: "×" }),
      el("input", { class: "fp-ic", type: "number", min: "1", value: String(c) }),
      el("button", { class: "fp-btn fp-sm", type: "button", text: "Quitar", onclick: () => { if (list.children.length > 1) row.remove(); } }));
    list.append(row);
  };
  if (initial && initial.length) initial.forEach(i => add(i.id_producto, i.cantidad));
  else add("PRD001", 2);
  const box = el("div", { class: "fp-items" }, list, el("button", { class: "fp-btn fp-sm", type: "button", text: "+ Agregar ítem", onclick: () => add() }));
  box.getValue = () => [...list.children]
    .map(r => ({ id_producto: r.querySelector(".fp-ip").value.trim(), cantidad: parseInt(r.querySelector(".fp-ic").value, 10) || 0 }))
    .filter(i => i.id_producto);
  box.setValue = items => {
    list.replaceChildren();
    (items && items.length ? items : [{ id_producto: "PRD001", cantidad: 2 }]).forEach(i => add(i.id_producto, i.cantidad));
  };
  return box;
}

function createPanel(q, opts = {}) {
  const t = Object.assign({ run: "Consultar", runMutation: "Ejecutar", loading: "Consultando", empty: "Sin resultados", fill: "Completá los datos y ejecutá" }, opts.text || {});
  const init = opts.initialValues || {};
  const st = { mode: init.modo && q.modes?.includes(init.modo) ? init.modo : (q.modes ? q.modes[0] : null), view: "tabla", last: null, running: false, nodes: [] };
  const ep = el("div", { class: "fp-ep" });
  const actions = el("div", { class: "fp-actions" });
  const form = el("form", { class: "fp-form", autocomplete: "off" });
  const runBtn = el("button", { class: "fp-btn fp-run", type: "button", text: q.mutation ? t.runMutation : t.run });
  const stat = el("span", { class: "fp-stat" });
  const out = el("div", { class: "fp-out" });
  const segBtns = ["tabla", "json"].map(v => el("button", { type: "button", class: v === "tabla" ? "on" : null, text: v === "tabla" ? "Tabla" : "JSON", onclick: () => {
    st.view = v;
    segBtns.forEach(b => b.classList.toggle("on", b.textContent.toLowerCase() === v));
    if (st.last) render();
  } }));
  const segWrap = el("div", { class: "fp-seg", hidden: !!opts.onSubmit }, segBtns);
  const bar = el("div", { class: "fp-bar" }, runBtn, segWrap, stat);
  const root = el("div", { class: "fp", style: `--qc:${q.color}` },
    el("div", { class: "fp-head" },
      el("div", { class: "fp-code", text: q.code }),
      el("div", { class: "fp-titles" }, el("div", { class: "fp-cat", text: `${CATS[q.cat].label} · ${q.engine}` }), el("h3", { class: "fp-title", text: q.title }), ep),
      actions),
    form,
    bar,
    out);

  let modeBtns = null;
  const hint = el("div", { class: "fp-hint" });
  if (q.modes) {
    modeBtns = q.modes.map(m => el("button", { type: "button", text: m, onclick: () => { st.mode = m; opts.onMode?.(m); applyMode(); } }));
    form.append(el("div", { class: "fp-modes" }, modeBtns));
    if (q.modeInfo) form.append(hint);
  }
  for (const f of q.fields || []) {
    let input;
    const iv = init[f.name] !== undefined ? init[f.name] : (f.def || "");
    if (f.type === "select") input = el("select", { name: f.name }, f.options.map(o => el("option", { value: o, text: o || "(sin cambio)", selected: o === iv })));
    else if (f.type === "items") input = itemsEditor(init[f.name]);
    else input = el("input", { name: f.name, value: iv, placeholder: f.ph || f.def || "", list: f.list || null });
    const wrap = el("label", { class: "fp-field" + (f.type === "items" ? " fp-wide" : "") }, el("span", { text: f.label + (f.req ? " *" : "") }), input);
    st.nodes.push({ f, wrap, input });
    form.append(wrap);
  }
  if (!form.children.length) form.hidden = true;

  const values = () => {
    const v = { modo: st.mode };
    for (const { f, input } of st.nodes) v[f.name] = f.type === "items" ? input.getValue() : input.value.trim();
    return v;
  };
  const setValues = (v = {}) => {
    if (v.modo && q.modes?.includes(v.modo)) st.mode = v.modo;
    for (const { f, input } of st.nodes) {
      if (!(f.name in v)) continue;
      if (f.type === "items") input.setValue(v[f.name]);
      else input.value = v[f.name] ?? "";
    }
    applyMode();
  };
  const build = strict => {
    const v = values();
    if (q.request) return q.request(v, strict);
    if (strict) for (const f of q.fields || []) if (f.req && !v[f.name]) throw new Error(`Completá el campo "${f.label}".`);
    return { method: q.method, path: q.path.replace(/\{(\w+)\}/g, (m, k) => (v[k] ? enc(v[k]) : m)) };
  };
  const refresh = () => {
    let r;
    try { r = build(false); } catch { r = { method: q.method, path: q.path }; }
    ep.textContent = `${r.method}  ${r.path}`;
  };
  function applyMode() {
    for (const { f, wrap } of st.nodes) wrap.hidden = !!(f.modes && !f.modes.includes(st.mode));
    modeBtns?.forEach(b => b.classList.toggle("on", b.textContent === st.mode));
    if (q.modeInfo) hint.textContent = q.modeInfo[st.mode];
    disarm();
    refresh();
  }
  function disarm() {
    st.armed = false;
    clearTimeout(st.armT);
    const modeLabel = opts.modeRun?.[st.mode] || (!opts.onSubmit && q.modeRun?.[st.mode]);
    runBtn.textContent = modeLabel || (q.mutation ? t.runMutation : t.run);
    runBtn.classList.toggle("fp-danger", !!q.confirmMode && st.mode === q.confirmMode);
  }

  function showError(msg, title, ms) {
    out.replaceChildren(el("div", { class: "fp-error" }, el("b", { text: title }), el("div", { text: msg })));
    stat.textContent = ms != null ? `${ms} ms` : "";
  }
  function render() {
    const { req, res } = st.last;
    const secs = q.sections ? q.sections(res.data, req) : [{ rows: res.data, cols: q.cols }];
    const total = secs.reduce((n, s) => n + s.rows.length, 0);
    stat.replaceChildren(el("b", { text: String(total) }), ` resultado${total === 1 ? "" : "s"} · HTTP ${res.status} · ${res.ms} ms`);
    if (st.view === "json") { out.replaceChildren(el("pre", { class: "fp-json", text: JSON.stringify(res.data, null, 2) })); return; }
    out.replaceChildren(...secs.map(s => el("div", { class: "fp-sec" },
      s.title ? el("h4", { text: s.title }) : null,
      s.rows.length ? table(s.rows, s.cols) : el("div", { class: "fp-empty", text: t.empty }))));
    if (q.note) out.append(el("div", { class: "fp-note", text: q.note(res.data) }));
  }

  async function run(skipConfirm = false) {
    if (st.running) return;
    let req;
    try { req = build(true); }
    catch (e) { showError(e.message, opts.text?.invalid || "Faltan datos"); opts.onError?.(e, q); return; }
    if (!skipConfirm && q.confirmMode && st.mode === q.confirmMode && !st.armed) {
      st.armed = true;
      runBtn.textContent = `Confirmar: ${st.mode.toLowerCase()} de ${values().id_cliente}`;
      st.armT = setTimeout(disarm, 4000);
      return;
    }
    disarm();
    if (opts.onSubmit) {
      opts.onSubmit(values(), req);
      return;
    }
    st.running = true;
    runBtn.disabled = true;
    stat.textContent = "";
    out.replaceChildren(el("div", { class: "fp-loading" }, el("i"), el("i"), el("i"), el("span", { text: t.loading })));
    try {
      const res = await call(req.method, req.path, req.body);
      st.last = { req, res };
      render();
      opts.onSuccess?.(q, req, res, q.mutation ? q.toast(res.data, req) : null);
    } catch (e) {
      st.last = null;
      showError(e.message, e.status ? `Error ${e.status}` : "Sin conexión", e.ms);
      opts.onError?.(e, q);
    } finally {
      st.running = false;
      runBtn.disabled = false;
    }
  }

  runBtn.onclick = () => run();
  form.addEventListener("input", refresh);
  form.addEventListener("submit", e => { e.preventDefault(); run(); });
  form.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); run(); } });
  applyMode();
  const shouldAutorun = !opts.onSubmit && (opts.autorun === true || (!q.mutation && opts.autorun !== false));
  if ((q.mutation || opts.onSubmit) && !shouldAutorun) out.append(el("div", { class: "fp-empty", text: t.fill }));
  if (shouldAutorun) setTimeout(() => run(true), opts.autorunDelay ?? 0);
  return { root, actions, bar, run, values, setValues, build, focus: () => form.querySelector("input,select")?.focus() };
}

function themeSwitcher(current, className = "fthemes") {
  const sel = el("select", { class: className, "aria-label": "Tema", onchange: e => { location.href = e.target.value; } },
    THEMES.map(t => el("option", { value: t.href, text: t.name, selected: t.id === current })));
  return sel;
}

return { el, store, pick, FMT, CATS, QUERIES, STATIONS, THEMES, API, byCode, call, get, ping, snapshot, Sound, createPanel, table, themeSwitcher };
})();
