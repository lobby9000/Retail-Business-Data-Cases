"""
export_modelo.py: Prepara los datos para las herramientas de BI y el dashboard web.

Produce:
  bi/fact_envios.csv      Tabla de hechos limpia con columnas derivadas (una fila = un envío)
  bi/dim_tienda.csv       Dimensión tienda
  bi/dim_calendario.csv   Dimensión calendario (una fila por día del semestre)
  dashboard/data.json     Agregados pre-calculados que consume el dashboard HTML

Uso:  python3 export_modelo.py
"""
import json

import numpy as np
import pandas as pd

TS = ["ts_orden", "ts_surtido_cedis", "ts_llegada_destino",
      "ts_disponible_cliente", "ts_entrega_final", "ts_promesa_entrega"]


def horas(a: pd.Series, b: pd.Series) -> pd.Series:
    """Diferencia a-b en horas (float). NaN si falta alguno de los dos."""
    return (a - b).dt.total_seconds() / 3600


def limpiar(env: pd.DataFrame) -> pd.DataFrame:
    """Aplica la limpieza documentada en 05_MEGA_CURSO.md §3.2 (misma lógica)."""
    env = env.drop_duplicates(subset="envio_id", keep="first").copy()
    env["categoria"] = (env.categoria.str.strip().str.lower()
                        .str.replace("soft line", "softline", regex=False)
                        .str.title())
    env["transportista"] = env.transportista.str.strip()
    mal = (env.ts_entrega_final < env.ts_orden) | (env.ts_surtido_cedis < env.ts_orden)
    env = env[~mal.fillna(False)]
    env.loc[env.valor_mercancia_mxn <= 0, "valor_mercancia_mxn"] = np.nan
    env.loc[env.piezas <= 0, "piezas"] = np.nan
    return env.reset_index(drop=True)


def construir_fact(env: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas derivadas. En BI conviene traer estas columnas YA calculadas
    desde la capa de datos (aquí pandas; en producción SQL/dbt): las medidas DAX
    quedan simples y el modelo es auditable."""
    f = env.copy()
    f["fecha_orden"] = f.ts_orden.dt.date            # llave hacia dim_calendario
    f["h_surtido"] = horas(f.ts_surtido_cedis, f.ts_orden)
    f["h_transito"] = horas(f.ts_llegada_destino, f.ts_surtido_cedis)
    f["h_ultima_milla"] = horas(f.ts_disponible_cliente, f.ts_llegada_destino)
    f["h_ciclo_operativo"] = horas(f.ts_disponible_cliente, f.ts_orden)
    f["h_recoleccion"] = horas(f.ts_entrega_final, f.ts_disponible_cliente)
    # Banderas 1/0 (no True/False): Power BI y Looker las agregan sin fricción
    f["flag_valido_kpi"] = (f.estado_final != "Cancelado").astype(int)
    f["flag_otif_operativo"] = (f.ts_disponible_cliente <= f.ts_promesa_entrega).astype(int)
    f["flag_otif_percibido"] = (f.ts_entrega_final <= f.ts_promesa_entrega).astype(int)
    f["segmento_valor"] = np.where(f.es_big_ticket, "Big Ticket", "Resto")
    return f


def construir_dim_calendario(f: pd.DataFrame) -> pd.DataFrame:
    """Tabla calendario: imprescindible en Power BI para inteligencia de tiempo.
    Una fila por día continuo (sin huecos), con atributos de agrupación."""
    fechas = pd.date_range(f.ts_orden.min().normalize(),
                           f.ts_orden.max().normalize(), freq="D")
    cal = pd.DataFrame({"fecha": fechas.date})
    d = pd.to_datetime(cal.fecha)
    cal["anio"] = d.dt.year
    cal["mes_num"] = d.dt.month
    cal["mes"] = d.dt.strftime("%Y-%m")
    cal["semana_iso"] = d.dt.isocalendar().week.astype(int)
    cal["dia_semana"] = d.dt.day_name()
    cal["es_fin_de_semana"] = d.dt.dayofweek.isin([5, 6]).astype(int)
    return cal


def agregados_dashboard(f: pd.DataFrame) -> dict:
    """Pre-agrega todo lo que pinta el dashboard. El HTML no recalcula nada:
    separar cómputo (Python) de presentación (JS) mantiene ambos simples."""
    k = f[f.flag_valido_kpi == 1]
    p90 = lambda s: float(s.quantile(0.90))
    meses = sorted(k.mes.unique().tolist()) if "mes" in k else None
    k = k.assign(mes=k.ts_orden.dt.strftime("%Y-%m"))
    meses = sorted(k.mes.unique().tolist())

    surtido = (k.pivot_table(index="cedis_origen", columns="mes",
                             values="h_surtido", aggfunc="median")
                 .round(1).reindex(columns=meses))

    canal = k.groupby("canal").agg(envios=("envio_id", "size"),
                                   operativo=("flag_otif_operativo", "mean"),
                                   percibido=("flag_otif_percibido", "mean")).round(4)

    occ = k[k.zona == "Occidente"]
    trans = occ.groupby("transportista").agg(
        envios=("envio_id", "size"),
        otif=("flag_otif_operativo", "mean")).round(4)
    trans = trans[trans.envios >= 200].sort_values("otif")

    cc = k[k.canal == "Click & Collect"]
    rec = cc.groupby("tienda_destino").agg(envios=("envio_id", "size"),
                                           mediana_h=("h_recoleccion", "median"))
    rec = rec[rec.envios >= 100].sort_values("mediana_h", ascending=False).round(1)

    bt = k.groupby("segmento_valor").agg(
        envios=("envio_id", "size"),
        otif=("flag_otif_operativo", "mean"),
        valor=("valor_mercancia_mxn", "sum"))
    bt["valor_riesgo"] = k[k.flag_otif_operativo == 0].groupby(
        "segmento_valor").valor_mercancia_mxn.sum()

    return {
        "kpis": {
            "otif": round(float(k.flag_otif_operativo.mean()), 4),
            "p90_h": round(p90(k.h_ciclo_operativo), 1),
            "envios": int(len(k)),
            "valor_riesgo_mxn": round(float(
                k.loc[k.flag_otif_operativo == 0, "valor_mercancia_mxn"].sum()), 0),
        },
        "meses": meses,
        "otif_mensual": k.groupby("mes").flag_otif_operativo.mean().round(4)
                         .reindex(meses).tolist(),
        "surtido_cedis": {c: [None if pd.isna(v) else float(v) for v in row]
                          for c, row in surtido.iterrows()},
        "canal": {c: {"envios": int(r.envios), "operativo": float(r.operativo),
                      "percibido": float(r.percibido)} for c, r in canal.iterrows()},
        "transportistas_occidente": {t: {"envios": int(r.envios), "otif": float(r.otif)}
                                     for t, r in trans.iterrows()},
        "otif_zona_occidente": round(float(occ.flag_otif_operativo.mean()), 4),
        "cc_tiendas_top": {t: {"envios": int(r.envios), "h": float(r.mediana_h)}
                           for t, r in rec.head(6).iterrows()},
        "cc_mediana_red": round(float(rec.mediana_h.iloc[6:].median()), 1),
        "big_ticket": {s: {"envios": int(r.envios), "otif": round(float(r.otif), 4),
                           "valor": round(float(r.valor), 0),
                           "valor_riesgo": round(float(r.valor_riesgo), 0)}
                       for s, r in bt.iterrows()},
    }


if __name__ == "__main__":
    import os
    os.makedirs("bi", exist_ok=True)
    os.makedirs("dashboard", exist_ok=True)

    env = pd.read_csv("datos/envios.csv", parse_dates=TS)
    tie = pd.read_csv("datos/tiendas.csv")

    fact = construir_fact(limpiar(env))
    cal = construir_dim_calendario(fact)

    fact.to_csv("bi/fact_envios.csv", index=False)
    tie.to_csv("bi/dim_tienda.csv", index=False)
    cal.to_csv("bi/dim_calendario.csv", index=False)

    with open("dashboard/data.json", "w", encoding="utf-8") as fh:
        json.dump(agregados_dashboard(fact), fh, ensure_ascii=False, indent=1)

    print("fact:", fact.shape, "| dim_tienda:", tie.shape, "| dim_calendario:", cal.shape)
    print("dashboard/data.json listo")
