# Diagnóstico de cumplimiento logístico de retail omnicanal (1S 2026)

Análisis end-to-end de una red logística tipo retail departamental: definición de
KPIs de entrega, detección de cuellos de botella con control de confusores y
significancia estadística, y un tablero interactivo para dirección.

>  **[Dashboard interactivo](https://lobby9000.github.io/Retail-Business-Data-Cases/dashboard/)** ·
>  **[Notebook del análisis](analisis.ipynb)**.
>
> *Datos sintéticos generados para este caso de estudio (ver `simulador/`); sin
> afiliación con ninguna empresa.*

El reporte mensual muestra OTIF global de **95.7%**, arriba de meta, pero
dirección percibe que "las entregas se sienten más lentas". Entregables: una
definición defendible del KPI de cumplimiento, la ubicación de los cuellos de
botella con evidencia, y el costo de no actuar.

## Cómo está estructurado el análisis

El notebook sigue el flujo de trabajo completo; estas son las decisiones clave en
cada paso (el detalle, con código anotado y salidas, está en `analisis.ipynb`):

**1. Auditoría antes de calcular.** `shape`, `dtypes`, `duplicated()` sobre la
llave, `value_counts()` como detector de categorías inconsistentes, y sanity
checks de valores físicamente imposibles: costos ≤ 0, envíos de 0 piezas
("envíos fantasma") y entregas anteriores a la orden,  que pueden deberse a husos
horarios, captura manual o errores manuales. También se cruzan los nulos contra
el estado del pedido: los 2,325 cancelados explican casi todos los huecos de
`ts_disponible_cliente`, y el remanente por etapa se propone como **métrica de
calidad de dato** para el tablero.

**2. Limpieza con linaje de dato.** Un log registra cada paso: 62,420 registros
crudos que llevan a la eliminacion de duplicados por llave (verificando primero 
que los duplicados fueran clones perfectos y no versiones contradictorias). Luego, 
exclusión de secuencias temporales imposibles y anulación (no borrado) de valores 
absurdos cuando el resto de la fila sigue siendo confiable.
Al último, cancelaciones fuera del denominador del KPI. Base final: **59,615 envíos**.

**3. Definición del KPI.** El OTIF se implementa en dos
versiones: *operativo* (pedido disponible vs. promesa) y *percibido* (pedido en
manos del cliente vs. promesa). En Click & Collect se abren ~35 puntos entre
ambas: la diferencia es la agenda del cliente, no la operación. El KPI logístico
corta en "disponible"; la recolección se mide aparte como métrica de tienda.
Para tiempos se reporta **mediana y P90**, no promedio: media > mediana en los
tres canales (cola derecha).

**4. Segmentación.** El 95.7% global es una compresión con pérdida; se descompone
por etapa del ciclo (surtido / tránsito / última milla) y por CEDIS × mes,
canal, zona × transportista y tienda.

**5. Validación estadística.** Ninguna unidad se compara contra el promedio
global: se compara contra sus **pares** (misma zona), y antes de señalar a una
tienda se calcula su **intervalo de Wilson**. Una tienda es "foco rojo" solo si
ni el techo de su intervalo alcanza el OTIF de su zona.

**6. Cuantificación en pesos.** Columna de exposición `valor_riesgo` (valor de
mercancía de los envíos fuera de promesa).

## Hallazgos

| # | Hallazgo | Evidencia |
|---|---|---|
| 1 | **CD-Tultitlán se degradó estructuralmente.** Todos los CEDIS empeoran en el pico de mayo (Hot Sale) y se recuperan en junio,  excepto uno, que pasa de ~8 a 14.3 h de surtido y no regresa. | Pivot CEDIS × mes; los otros 4 CEDIS actúan como grupo de control |
| 2 | **El Ranking de "peores tiendas".** Las 10 peores compartían zona; condicionando por zona, la variable explicativa es TransBajio, que opera 25 pts abajo de sus pares, solo en Occidente (en Norte se comporta normal). Con Wilson, 1 de 61 tiendas es significativamente peor que su zona. | OTIF transportista × zona; IC de Wilson por tienda |
| 3 | **Seis mostradores de Click & Collect triplican el tiempo de recolección.** El corte logístico ya se cumplía: el problema vive en notificación/mostrador ; hallazgo empaquetado para Operación de Tiendas. | Mediana de h_recoleccion por tienda vs. red |
| 4 | **La mercancía cara pasa por los nodos rotos.** Big Ticket: ~31% de envíos, ~87% del valor, ~75% de los $10.0M MXN fuera de promesa | Descomposición de valor en riesgo por segmento |

## Estructura del repo

```
├── README.md
├── analisis.ipynb        Análisis completo, anotado y ejecutado
├── export_modelo.py      Modelo estrella para BI + agregados del dashboard
├── datos/                envios.csv · tiendas.csv (insumos)
├── bi/                   fact_envios · dim_tienda · dim_calendario (generado)
├── dashboard/            index.html — tablero interactivo (generado data.json)
└── simulador/            generar_datos.py — generador del dataset sintético
```

## Reproducir

```bash
pip install pandas numpy
python3 simulador/generar_datos.py   # regenera datos/ (semilla fija)
jupyter notebook analisis.ipynb      # o ábrelo directo: ya trae las salidas
python3 export_modelo.py             # regenera bi/ y dashboard/data.json
```

## Stack

`python` `pandas` `numpy` `SQL` `Chart.js` · modelo listo para
`Power BI` / `Looker Studio` en `bi/`
