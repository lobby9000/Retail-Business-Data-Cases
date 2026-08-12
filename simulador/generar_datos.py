"""
Generador de datos sintéticos: red logística tipo retail omnicanal (MX).
Genera datos/envios.csv y datos/tiendas.csv.

"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(20260810)

# ----------------------------------------------------------------- catalogos
CEDIS = {
    "CD-TULTITLAN": "Metro",
    "CD-HUEHUETOCA": "Metro",
    "CD-GUADALAJARA": "Occidente",
    "CD-MONTERREY": "Norte",
    "CD-PUEBLA": "Sureste",
}
ZONAS = ["Metro", "Occidente", "Norte", "Sureste", "Bajio"]
ZONA_A_CEDIS = {
    "Metro": "CD-TULTITLAN",
    "Bajio": "CD-HUEHUETOCA",
    "Occidente": "CD-GUADALAJARA",
    "Norte": "CD-MONTERREY",
    "Sureste": "CD-PUEBLA",
}

tiendas = []
tid = 1000
for zona in ZONAS:
    n = {"Metro": 22, "Occidente": 10, "Norte": 12, "Sureste": 9, "Bajio": 8}[zona]
    for i in range(n):
        cadena = "Liverpool" if rng.random() < 0.55 else "Suburbia"
        tiendas.append({
            "tienda_id": f"T{tid}",
            "nombre_tienda": f"{cadena} {zona} {i+1:02d}",
            "cadena": cadena,
            "zona": zona,
            "formato": rng.choice(["Departamental", "Boutique", "Express"], p=[.6, .25, .15]),
            "cedis_asignado": ZONA_A_CEDIS[zona],
            "m2_piso_venta": int(rng.normal(6500 if cadena == "Liverpool" else 3200, 1200)),
        })
        tid += 1
tiendas = pd.DataFrame(tiendas)

CATEGORIAS = {
    # categoria: (peso, es_big_ticket, valor_medio)
    "Softline":            (0.34, False, 900),
    "Hardline":            (0.16, False, 2200),
    "Electronica":         (0.14, True, 18000),
    "Linea Blanca":        (0.10, True, 14500),
    "Muebles":             (0.08, True, 22000),
    "Belleza":             (0.12, False, 750),
    "Juguetes":            (0.06, False, 650),
}
cats = list(CATEGORIAS)
pesos = np.array([CATEGORIAS[c][0] for c in cats]); pesos = pesos / pesos.sum()

CANALES = ["Domicilio", "Click & Collect", "Tienda a Tienda"]
TRANSPORTISTAS = ["LogiMex", "EnviaYa", "TransBajio", "Flota Propia", "PaqueteExpress"]

N = 62_000
inicio = pd.Timestamp("2026-01-01")

# ------------------------------------------------------------------- eventos
z = rng.choice(ZONAS, N, p=[.38, .16, .20, .14, .12])
tiendas_por_zona = {zz: tiendas.loc[tiendas.zona == zz, "tienda_id"].to_numpy() for zz in ZONAS}
tienda = np.array([rng.choice(tiendas_por_zona[zz]) for zz in z])
mapa_cadena = tiendas.set_index("tienda_id")["cadena"]
cadena = mapa_cadena.loc[tienda].to_numpy()
cedis = np.array([ZONA_A_CEDIS[zz] for zz in z])

categoria = rng.choice(cats, N, p=pesos)
big_ticket = np.array([CATEGORIAS[c][1] for c in categoria])
valor = np.array([max(120, rng.normal(CATEGORIAS[c][2], CATEGORIAS[c][2] * .35)) for c in categoria])
piezas = np.where(big_ticket, rng.integers(1, 3, N), rng.integers(1, 6, N))

canal = np.where(
    big_ticket,
    rng.choice(CANALES, N, p=[.72, .10, .18]),
    rng.choice(CANALES, N, p=[.48, .38, .14]),
)

# fecha de orden con estacionalidad + pico tipo Hot Sale (mediados de mayo)
dia = rng.integers(0, 181, N).astype(float)
pico = rng.random(N) < 0.10
dia[pico] = rng.normal(134, 4, pico.sum())          # ~14-18 de mayo
dia = np.clip(dia, 0, 180)
hora = rng.normal(14, 4.5, N).clip(6, 23)
ts_orden = inicio + pd.to_timedelta(dia, "D") + pd.to_timedelta(hora, "h")
ts_orden = pd.Series(ts_orden)

carga = pd.Series(dia).round().map(pd.Series(dia).round().value_counts()).to_numpy()
factor_carga = 1 + 0.45 * (carga / np.median(carga) - 1).clip(0, None)

# --- Etapa 1: surtido en CEDIS (picking + packing) --------------------------
h_pick = rng.gamma(2.2, 3.0, N) + 1.5
h_pick *= np.where(big_ticket, 1.55, 1.0)
h_pick *= factor_carga
# SEÑAL 1: CD-TULTITLAN se degrada progresivamente a partir de abril
degrada = (cedis == "CD-TULTITLAN") & (dia > 90)
h_pick[degrada] *= 1 + 0.9 * ((dia[degrada] - 90) / 90)
ts_surtido = ts_orden + pd.to_timedelta(h_pick, "h")

# --- Etapa 2: transito CEDIS -> destino ------------------------------------
base_transito = {"Metro": 14, "Bajio": 22, "Occidente": 30, "Norte": 34, "Sureste": 38}
h_tran = np.array([base_transito[zz] for zz in z]) * rng.gamma(4, 0.25, N)
transportista = rng.choice(TRANSPORTISTAS, N, p=[.28, .18, .16, .24, .14])
# SEÑAL 2: TransBajio en Occidente y con Big Ticket es malo (y empeora)
malo = (transportista == "TransBajio") & (z == "Occidente")
h_tran[malo] *= 1.7
h_tran[malo & big_ticket] *= 1.35
ts_llegada = ts_surtido + pd.to_timedelta(h_tran, "h")

# --- Etapa 3: ultima milla / disponibilidad --------------------------------
h_ult = np.where(canal == "Domicilio", rng.gamma(3, 4.0, N), rng.gamma(1.6, 1.6, N))
h_ult *= np.where(big_ticket & (canal == "Domicilio"), 1.9, 1.0)  # requiere cita e instalacion
ts_disponible = ts_llegada + pd.to_timedelta(h_ult, "h")

# --- Etapa 4: recoleccion del cliente (solo Click & Collect) ---------------
h_reco = np.where(canal == "Click & Collect", rng.gamma(2.0, 11.0, N), np.nan)
# SEÑAL 3 (trampa): 6 tiendas con recoleccion lentisima -> infla el "tiempo total"
# aunque la operacion logistica ya habia cumplido. Ojo al definir el KPI.
tiendas_lentas = tiendas.tienda_id.to_numpy()[[3, 11, 27, 40, 52, 58]]
lenta = np.isin(tienda, tiendas_lentas) & (canal == "Click & Collect")
h_reco = np.where(lenta, h_reco * 3.1, h_reco)
ts_entrega = ts_disponible + pd.to_timedelta(np.nan_to_num(h_reco), "h")

# --- Promesa de entrega ----------------------------------------------------
promesa_dias = np.where(canal == "Click & Collect", 2, np.where(big_ticket, 5, 3))
promesa_dias = promesa_dias + np.where(np.isin(z, ["Norte", "Sureste"]), 1, 0)
ts_promesa = ts_orden.dt.normalize() + pd.to_timedelta(promesa_dias.astype(float), "D") + pd.Timedelta(hours=20)

# --- Estado final ----------------------------------------------------------
p_cancel = 0.028 + 0.03 * big_ticket
estado = np.where(rng.random(N) < p_cancel, "Cancelado", "Entregado")
p_dev = 0.05 + 0.06 * (categoria == "Softline")
estado = np.where((estado == "Entregado") & (rng.random(N) < p_dev), "Devuelto", estado)

df = pd.DataFrame({
    "envio_id": [f"E{2026_000000 + i}" for i in range(N)],
    "orden_id": [f"O{rng.integers(10**7, 10**8)}" for _ in range(N)],
    "sku": [f"SKU-{rng.integers(100000, 999999)}" for _ in range(N)],
    "categoria": categoria,
    "es_big_ticket": big_ticket,
    "cadena": cadena,
    "canal": canal,
    "zona": z,
    "cedis_origen": cedis,
    "tienda_destino": tienda,
    "transportista": transportista,
    "piezas": piezas,
    "valor_mercancia_mxn": valor.round(2),
    "costo_envio_mxn": (valor * rng.uniform(.01, .05, N) + 45).round(2),
    "ts_orden": ts_orden,
    "ts_surtido_cedis": ts_surtido,
    "ts_llegada_destino": ts_llegada,
    "ts_disponible_cliente": ts_disponible,
    "ts_entrega_final": ts_entrega,
    "ts_promesa_entrega": ts_promesa,
    "estado_final": estado,
})

# cancelados: no completan el ciclo
canc = df.estado_final == "Cancelado"
corte = rng.random(canc.sum()) < 0.5
idx = df.index[canc]
df.loc[idx[corte], ["ts_llegada_destino", "ts_disponible_cliente", "ts_entrega_final"]] = pd.NaT
df.loc[idx[~corte], ["ts_disponible_cliente", "ts_entrega_final"]] = pd.NaT

# ------------------------------------------------------- suciedad realista
# 1) categoria con formatos inconsistentes
m = rng.random(N) < 0.06
df.loc[m, "categoria"] = df.loc[m, "categoria"].str.upper()
m = rng.random(N) < 0.04
df.loc[m, "categoria"] = df.loc[m, "categoria"].str.lower().str.replace("softline", "soft line")
# 2) transportista con espacios y mayusculas
m = rng.random(N) < 0.05
df.loc[m, "transportista"] = "  " + df.loc[m, "transportista"] + " "
# 3) nulos en timestamps de etapas intermedias (fallas de captura)
for col, p in [("ts_surtido_cedis", .012), ("ts_llegada_destino", .02)]:
    df.loc[rng.random(N) < p, col] = pd.NaT
# 4) valores negativos / cero
df.loc[rng.random(N) < 0.004, "valor_mercancia_mxn"] *= -1
df.loc[rng.random(N) < 0.003, "piezas"] = 0
# 5) duplicados exactos de envio_id
dups = df.sample(420, random_state=7)
df = pd.concat([df, dups], ignore_index=True)
# 6) unos pocos registros con entrega ANTES de la orden (error de sistema)
bad = df.sample(60, random_state=11).index
df.loc[bad, "ts_entrega_final"] = df.loc[bad, "ts_orden"] - pd.Timedelta(days=2)

df = df.sample(frac=1, random_state=3).reset_index(drop=True)

for c in ["ts_orden", "ts_surtido_cedis", "ts_llegada_destino",
          "ts_disponible_cliente", "ts_entrega_final", "ts_promesa_entrega"]:
    df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d %H:%M:%S")

df.to_csv("datos/envios.csv", index=False)
tiendas.to_csv("datos/tiendas.csv", index=False)
print(df.shape, tiendas.shape)
print(df.head(3).T)
