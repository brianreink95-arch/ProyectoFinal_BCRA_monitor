# Validación del diseño relacional — 4 de octubre de 2026 (Buenos Aires)

La última consolidación completa se ejecutó sin red y exportó exactamente las
12 tablas del contrato: 2 A, 3 B y 7 C. Se validaron 12 claves primarias, 9
relaciones foráneas, tipos y nulabilidad; ninguna tabla tiene referencias huérfanas.

- Los 332 archivos de fuentes originales conservan su SHA-256.
- A conserva 65 series y 41.687 observaciones, iguales en valor original y
  analítico a la entrega previa; la excepción 1199 permanece explícita.
- B conserva 46.586 observaciones de 13 capturas completas y los mismos valores
  TEA/CFTEA. Su observacion_id es reproducible y único; la captura incompleta
  permanece en snapshots sin ofertas.
- C conserva 100 CUIT, 102 pertenencias, 28.968 empresa-acreedor-mes y 2.400
  empresa-mes. Las métricas compartidas del panel coinciden con la entrega previa.
  Los saldos agregados reconcilian con el detalle positivo.
- Seis pruebas semánticas C y ocho pruebas relacionales aprobadas. Se verifica
  rechazo de PK duplicada, FK huérfana, fecha inválida y booleano desconocido.
- La adquisición A se simuló con datos guardados y el nuevo contrato en staging.
- La nueva adquisición C se simuló con las respuestas guardadas de las 100
  empresas: produce solo cuatro CSV de insumos, sin target, paneles exploratorios
  ni bundle ZIP. La transformación produce siete tablas y los mismos hechos.
- Sintaxis de scripts y cuatro notebooks comprobada; las cuatro CLI responden
  a --help. La carga real del notebook conjunto mantiene los conteos A/B/C.
- La exportación CSV escribe temporalmente y verifica encabezado/cantidad de
  registros antes de publicar cada archivo. El puntero ABC solo cambia al completar.

No se consultó BCRA en vivo, no se entrenaron modelos y no se reejecutaron todos
los gráficos. B no cambió su adquisición; sus nuevas tablas se comprobaron con
las fuentes guardadas. Windows y la instalación en Python 3.14 no se ejecutaron
en este entorno; las verificaciones usan Python 3.12 y pandas 2.2.3.

El informe JSON registra corrida, tablas y conteos. Esta evidencia original
certifica tablas, no entrenamiento ni scores. La primera matriz de features ICC
se validó posteriormente, como se detalla al final; los scores siguen sin existir.

Repetir desde la raíz:

```bash
python docs/validar_semantica.py
python docs/validar_relacional.py
```

## Primera matriz ICC — evidencia posterior

Implementada en [ml/features.py](../ml/features.py), con diccionario en
[features_icc.md](features_icc.md). Solo A de la consolidación ABC completa
`20261005_011327_837742`, sin adquisición online ni modificación de fuentes.
La matriz representa hipotecarios ML a personas humanas, no un ICC nacional.

- 321 filas mensuales, 1999-12–2026-08, PK única `(fecha_mes, segmento)` y
  calendario continuo. 119 elegibles consecutivas, 2016-08–2026-06; 202 no
  elegibles conservadas con motivos por feature.
- Seis features; cero infinitos. Fórmulas verificadas directamente con los datos
  de junio de 2026 y mediante casos sintéticos de rezagos, ventanas y denominadores.
- Los cinco destinos hipotecarios reconcilian con el total en los 319 meses de
  stock: diferencia máxima 2, dentro de la tolerancia inicial documentada de 3.
  No certifica la escala absoluta ni habilita sumar otros stocks.
- 17 pruebas ICC, 6 semánticas y 8 relacionales: **31 aprobadas**. Cubren huecos,
  ceros, warm-up, PK nulas/duplicadas, fechas, no uso de futuro, rechazo de tablas
  alteradas/corridas incompletas, catálogo, excepción 1199 y exportación única.
- CLI ejecutada dos veces con idénticos inputs/código: mismo CSV y SHA-256
  `c1a517d0150e8997cee50e1d447ef3f8df5271ca833024b9e1033e896ae9db15`.
- Los 332 hashes de fuentes originales coinciden con `source_sha256` de la
  consolidación. Las 12 tablas originales y el puntero latest no se reemplazaron.
- Esta nueva validación sí se ejecutó en **Windows, Python 3.14.6, pandas 2.3.3
  y NumPy 2.5.3**, a diferencia de la evidencia original de tablas descrita arriba.
  Sintaxis y diagnósticos del código nuevo sin errores.

Salida única: [icc.csv](../data_analytics/features/20261005_011327_837742/icc.csv),
fuera del contrato de 12 tablas. No hay score productivo, modelo ni PCA; el ajuste posterior de referencias
empíricas del baseline se documenta en la sección siguiente.
La disponibilidad histórica sigue sin verificarse: estos controles prueban
construcción retrospectiva por referencia, no una evaluación point-in-time.

```bash
python ml/features.py
python -m unittest docs.validar_features_icc docs.validar_semantica docs.validar_relacional -v
```

## Splits y referencias experimentales ICC hipotecario

[ml/baseline.py](../ml/baseline.py) se ejecutó sin red sobre la matriz persistida
de la misma consolidación. No modifica sus seis features ni el CSV original.
El hash de la metodología guardada coincide con la consolidación; se verificaron
la posibilidad de arrastres del BCRA y la distinta población de tasa/stock.

- Splits fijos por calendario: 65 meses train (2016-08–2021-12), 24 de validación
  (2022–2023) y 30 de evaluación retrospectiva (2024–2026-06). Este bloque ya fue
  inspeccionado: no se presenta como test final intacto. Desde 2026-07 no se
  puntúa, aunque futuras filas sean elegibles; todavía falta un test no inspeccionado.
- Tres referencias predefinidas, con percentiles de rango medio ajustados solo
  sobre train. Pesos por dimensión: 50% crecimiento nominal / 50% tasa UVA;
  composición y volatilidad permanecen como descriptores sin peso.
- Las correlaciones señaladas se reproducen. En train, Pearson de crecimientos
  es 0,9674; en 119 meses es 0,9354. Se guardan diagnósticos de ajuste únicamente
  de train y sensibilidad de train/validación, sin escoger una variante por test.
- Extremos 2024-02, 2024-10 y 2024-11 conservados. La fórmula y las tablas fuente
  coinciden; la causa económica/metodológica no puede determinarse con los
  agregados y la descripción general disponibles. No se winsorizan ni excluyen.
- En validación, 18/24 tasas UVA están fuera del rango de train: saturación de
  ECDF y cambio de distribución documentados, no subsanados recalibrando con test.
- **45 pruebas aprobadas:** 14 baseline, 17 features, 6 semánticas y 8 relacionales.
  Incluyen cambios artificiales fuera de train que no alteran referencias ni
  resultados anteriores, empates, reserva sin puntuar, pesos, controles de PK,
  fuentes/matrices alteradas, relectura de tipos y reproducción de ambos outputs.
- Dos ejecuciones reales produjeron el mismo CSV y JSON, con los siguientes hashes:
  - CSV: `db1288d811f16add11660d14e93065540eb0de6a9412f72ef7e0cc41e419df26`.
  - JSON: `a20454a5d4ff96ae2e286b0e473fadd3aa5f62d87fdfef61f72524d7309a396f`.
- Los 332 archivos fuente y la matriz original mantienen sus hashes. Las tablas
  relacionales, latest y los notebooks no se modificaron. Sintaxis/diagnósticos
  nuevos sin errores; no se añadieron dependencias.

Solo se exportan [icc_hipotecario.csv](../data_analytics/baselines/20261005_011327_837742/icc_hipotecario.csv)
y [protocolo_icc.json](../data_analytics/baselines/20261005_011327_837742/protocolo_icc.json):
comparación experimental y artefacto reproducible de splits/referencias para
futuro entrenamiento. No son un score validado, régimen ni salida web.

```bash
python ml/baseline.py
python -m unittest docs.validar_baseline_icc docs.validar_features_icc docs.validar_semantica docs.validar_relacional -v
```
