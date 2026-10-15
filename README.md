# Omnichannel retail delivery diagnostics (H1 2026)

End-to-end analysis of a department-store delivery network: a defensible on-time-in-full (OTIF) KPI, bottlenecks located with confounder control and statistical tests, and an interactive dashboard for management.

**[Interactive dashboard](https://lobby9000.github.io/Retail-Business-Data-Cases/dashboard/)** · **[Analysis notebook](analisis.ipynb)** · [Versión en español](README.es.md)

**Try it in your browser:** the [`retail` demo](https://lobby9000.github.io/professional.html?app=terminal&run=retail) on my site recomputes the Wilson intervals of the 61 stores and flags the same store as the notebook.

> Synthetic data generated for this case study (see `simulador/`). No affiliation with any company. Code, folder and column names are in Spanish to match the Mexican retail context.

## The problem

The monthly report showed an overall OTIF of **95.7%**, above target, yet management felt that deliveries were getting slower. The brief: a defensible definition of the delivery KPI, evidence of where the bottlenecks are, and the cost of doing nothing.

## Highlights

- **Data lineage:** 62,420 raw records reduced to **59,615 shipments** through a logged cleaning process. Duplicates were confirmed as exact clones before removal, impossible time sequences were excluded, absurd values were nulled rather than deleted, and cancellations were kept out of the KPI denominator.
- **Two KPIs, not one:** *operational* OTIF (order ready vs promise) and *perceived* OTIF (order in the customer's hands vs promise). In Click & Collect they diverge by about 35 points, which is explained by when customers collect, not by operations.
- **Peers, not averages:** each store is compared with the stores in its own zone using **Wilson intervals**. Only 1 of 61 stores is significantly worse than its zone.

## Findings

| # | Finding | Evidence |
|---|---|---|
| 1 | **DC Tultitlán degraded structurally.** Every distribution centre slows down in the May peak (Hot Sale) and recovers in June except one, whose picking time goes from about 8 h to 14.3 h and stays there. | DC × month pivot, with the other four DCs as a control group |
| 2 | **The "worst stores" ranking is a carrier effect.** The ten worst stores shared a zone. Conditioning on zone, the explanatory variable is the carrier TransBajio, which runs 25 points below its peers in the West zone only. | OTIF by carrier × zone, Wilson interval per store |
| 3 | **Six Click & Collect counters triple collection time.** The logistics cut-off was already met, so the problem lives in customer notification and counter service. The finding is packaged for Store Operations. | Median collection hours per store vs the network |
| 4 | **Expensive goods travel through the broken nodes.** Big-ticket items are about 31% of shipments but 87% of value, and 75% of the MXN 10.0M delivered outside the promised window. | Value-at-risk breakdown by segment |

## Method

1. **Audit before computing.** Shape, dtypes, duplicate keys, category consistency and physically impossible values (non-positive costs, zero-piece shipments, deliveries before the order). Missing values are cross-checked against order status: the 2,325 cancellations explain almost every gap in `ts_disponible_cliente`, and the remainder by stage becomes a data-quality metric on the dashboard.
2. **Cleaning with lineage.** Every step is logged, from 62,420 raw records to the 59,615-shipment base.
3. **KPI definition.** Operational and perceived OTIF. Lead times are reported as median and P90 instead of mean, because all three channels are right-skewed.
4. **Segmentation.** By cycle stage (picking, transit, last mile) and by DC × month, channel, zone × carrier, and store.
5. **Statistical validation.** Units are compared with their peers. A store is flagged only if even the upper bound of its Wilson interval falls short of its zone's OTIF.
6. **Impact in money.** A `valor_riesgo` exposure column holds the value of goods delivered outside the promise.

## Repository structure

```
├── README.md            English (this file)
├── README.es.md         Spanish version
├── analisis.ipynb       Full annotated analysis, with outputs
├── export_modelo.py     Star schema for BI and dashboard aggregates
├── datos/               envios.csv, tiendas.csv (inputs)
├── bi/                  fact_envios, dim_tienda, dim_calendario (generated)
├── dashboard/           index.html, interactive dashboard reading data.json
└── simulador/           generar_datos.py, synthetic data generator
```

## Reproduce

```bash
pip install -r requirements.txt
python3 simulador/generar_datos.py   # regenerates datos/ (fixed seed)
jupyter notebook analisis.ipynb      # or open it directly: outputs are saved
python3 export_modelo.py             # regenerates bi/ and dashboard/data.json
```

## Stack

Python · pandas · NumPy · Chart.js · star schema ready for Power BI or Looker Studio (`bi/`)

## Licence

Code released under the [MIT licence](LICENSE).

---

Part of the portfolio of Luis Ángel Quiroz López · [lobby9000.github.io](https://lobby9000.github.io) · [LinkedIn](https://www.linkedin.com/in/llqq) · [GitHub](https://github.com/lobby9000)
