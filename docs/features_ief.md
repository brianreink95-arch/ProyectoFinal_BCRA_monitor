# Matriz IEF 0.2 — Base C y tratamiento de datos

Implementada el 21 de octubre de 2026 (Buenos Aires). Consumidor inmediato:
baseline interpretable y posterior Isolation Forest del plan `plan_ief.md`.
Este módulo prepara y trata datos. El bosque está implementado por separado
en `ml/isolation_ief.py`: ver `modelo_ief.md`.
El baseline de prioridad mensual ya está implementado: ver `baseline_ief.md`.
La versión 0.1 conserva la matriz inicial; la vigente es 0.2.

## Entrada, unidad y claves

`ml/ief.py` lee `data_analytics/latest.json` y exige una consolidación ABC
completa con contrato 2.0. Verifica hashes, tipos, PK/FK de las siete tablas C y
la referencia al IPC nacional. Recalcula la identidad nominal por factor IPC
para comprobar los saldos reales de empresa y de acreedor. También reconcilia
saldos, cantidad de acreedores, HHI, situación y proporciones con el detalle.
Los tres mayores y tres menores crecimientos de train se verifican además contra
las capturas JSON originales, cuyo hash debe coincidir con el de la consolidación.

La unidad es `(cuit_normalizado, fecha)`. El CUIT se conserva como texto; fecha
es el primer día del mes de referencia. `cutoff_referencia` es el cierre de ese
mes y limita las variables a información de ese período o anterior. Las fuentes
son retrospectivas: el cutoff no acredita que los datos fueran públicos entonces.

Se parte del universo de empresas y una grilla mensual continua. Un hueco se
conserva con `fila_presente_fuente=False`, sin inventar deuda cero. Un join
many-to-one agrega razón social, grupo informado y perfil sectorial; las
pertenencias múltiples no multiplican empresas. No hay join con ofertas B.

`deuda_total_positiva` conserva miles de ARS nominales.
`deuda_total_positiva_constante_dic2016` conserva miles de ARS con poder de compra
de diciembre de 2016: `R_t = nominal_t * 100 / IPC_nacional_t`.
Se usa el factor del mismo mes; no se arrastra un IPC faltante.
Las proporciones y el HHI provienen de saldos positivos y no se deflactan.

## Los seis predictores y su orden

| Columna | Definición | Unidad |
| --- | --- | --- |
| `deuda_log_ratio_real_3m` | `ln(R_t) - ln(R_t-3)` | Razón logarítmica, adimensional |
| `acreedores_delta_3m` | Acreedores con saldo positivo en t menos cantidad en t-3 | Cantidad |
| `hhi_deuda_positiva` | Suma de cuadrados de participaciones de saldos positivos en t | Índice 0–1 |
| `situacion_max_activa` | Máxima situación activa conocida, según el criterio de C | Categoría ordinal |
| `pct_deuda_situacion_2_mas` | Porcentaje en situación 2 más porcentaje en situación 3 o superior | Porcentaje 0–100 |
| `pct_deuda_situacion_2_mas_delta_3m_pp` | Proporción anterior en t menos su valor en t-3 | Puntos porcentuales |

El crecimiento porcentual original `deuda_var_real_3m_pct = 100 * (R_t / R_t-3 - 1)`
permanece en el CSV como contexto. El modelo usará exclusivamente la versión
logarítmica, junto con las otras cinco variables de la tabla.

Un cambio a tres meses usa extremos separados por tres meses y exige los
cuatro meses observados `[t-3, t-2, t-1, t]`. En crecimiento real, los cuatro
deben estar ajustados por IPC y el saldo de t-3 debe ser positivo. Para cantidad
y proporciones se exigen valores conocidos en ambos extremos. Un cero intermedio
observado no es un hueco; una base cero impide calcular crecimiento relativo.

Una proporción faltante no se suma como cero. La falta de deuda activa no se
convierte en situación 1. El HHI y el crecimiento no tienen una dirección de
riesgo automática: concentración estable, desendeudamiento y expansión pueden
expresar fenómenos diferentes.

CUIT, nombres, grupo, perfil sectorial, montos absolutos, cantidad absoluta de
acreedores, flags y fechas son contexto. El consumidor debe seleccionar
exclusivamente `predictores_ordenados` del JSON, nunca todas las columnas numéricas.
Las señales legales constantes y las etiquetas futuras no integran esta matriz.

## Tratamiento fijado antes del primer modelo

| Aspecto | Regla aplicada |
| --- | --- |
| Crecimiento real extremo | Transformación fija `ln(R_t) - ln(R_t-3)`, calculada sobre la grilla completa antes de filtrar filas. |
| Otros cinco predictores | Identidad; se conservan unidades, decimales y categorías ordinales. |
| Faltantes, deuda base cero y meses sin deuda activa | Permanecen sin imputar y con sus motivos; no entran al entrenamiento. |
| Valores extremos válidos | Se conservan; no hay recorte, winsorización ni eliminación por percentiles. |
| Referencias de diagnóstico | Mínimo, p01, mediana, p99 y máximo usando solo las 875 filas elegibles de train. |
| Columnas constantes | Si alguna de las seis es constante en train, se detiene la preparación para revisar el protocolo. No se descarta silenciosamente. |
| Escalado | No se ajusta StandardScaler ni MinMaxScaler para este primer bosque. |

El logaritmo comprime los saltos porcentuales y conserva el signo y el orden del
crecimiento. Una duplicación vale `ln(2)` y una reducción a la mitad vale `-ln(2)`.
No convierte una entrada desde deuda cero en un crecimiento calculable. Se usa
la diferencia de logaritmos de saldos positivos, evitando un cociente intermedio
que pueda desbordar o redondear el porcentaje a -100%.

Esta decisión cambia la geometría de la variable: no se asume que preserve los
puntajes de Isolation Forest ni que mejore su desempeño. Se fijó tras explorar
el panel, antes de entrenar. El contraste posterior sigue siendo exploratorio.
En la etapa del modelo se comparará, como sensibilidad predefinida, el bosque
con crecimiento porcentual original frente al principal con crecimiento logarítmico,
sin elegir retrospectivamente por los casos de evaluación final.

La auditoría de los seis extremos de train coincide con los saldos positivos de
las capturas originales. Esto descarta una discrepancia entre esas capturas y
los agregados revisados; no prueba que los saltos reflejen únicamente actividad
económica, ni excluye problemas o cambios de reporte en la fuente.

| Referencia de train | Mínimo | Mediana | Máximo |
| --- | ---: | ---: | ---: |
| Crecimiento porcentual original | -99,634% | 4,682% | 256.517,410% |
| Crecimiento logarítmico | -5,611 | 0,0458 | 7,850 |

`crecimiento_fuera_rango_train` marca valores logarítmicos fuera del mínimo/máximo
congelados en train. Es contexto de revisión, no un predictor ni una clasificación
de riesgo. Entre las filas elegibles se marca una de validación y nueve de
evaluación; ninguna se elimina o recorta. Los percentiles p01/p99 solo describen
la distribución y no definen cortes ni exclusiones.

`tratar_matriz(frame, referencias=...)` permite reutilizar las referencias
persistidas sin reajustarlas, aun si el lote de aplicación no contiene train.
La transformación requiere conservar el calendario y los tres meses de historia
previos a cada fila; no se desplazan lags después de filtrar elegibilidad.

## Elegibilidad y bloques temporales

`elegible_ief` exige mes observado, deuda activa, las seis variables disponibles
y pertenencia a un bloque del protocolo. No se imputa ni escala ninguna columna.
Las filas excluidas conservan valores disponibles y motivos separados por `;`:
historia insuficiente, huecos, falta de ajuste, deuda base cero, ausencia de deuda,
features no disponibles o fecha fuera del protocolo. Los motivos no son excluyentes.

| Bloque | Meses | Filas | Elegibles | No elegibles |
| --- | --- | ---: | ---: | ---: |
| Train | Ago. 2024–jul. 2025 | 1.200 | 875 | 325 |
| Validación | Ago. 2025–ene. 2026 | 600 | 587 | 13 |
| Evaluación retrospectiva | Feb.–jul. 2026 | 600 | 585 | 15 |
| Total | 24 meses, 100 empresas | 2.400 | 2.047 | 353 |

Se preservan las 47 filas sin deuda activa. Las primeras 300 filas, de agosto
a octubre de 2024, no tienen tres meses previos suficientes. Estas causas se
solapan: no se deben sumar para explicar las 353 exclusiones. Hay además 46 filas
con saldo base cero. El JSON incluye el recuento completo de cada motivo.

Todas las empresas de un mes comparten bloque. Los lags pueden usar historia
del bloque previo; las ventanas nunca consultan meses posteriores a t. Las fechas
posteriores a julio de 2026 quedan fuera del protocolo hasta definir una versión
nueva. No hay etiqueta de deterioro t+1, ni estimación de probabilidades, en esta etapa.

La matriz identifica columnas constantes con filas elegibles de train y detiene
la publicación si aparece alguna entre los predictores tratados. El panel completo ya fue
explorado: la evaluación posterior al ajuste no es un test histórico intacto.

## Archivos, reproducción y verificación

Resultados incluidos:

```text
data_analytics/modelos_ief/20261006_231124_214604/v0.2/
  features_ief.csv
  protocolo_resultados.json
```

El CSV conserva grano, contexto, predictores, disponibilidad, elegibilidad y
motivos. El JSON registra fórmulas, unidades, orden de predictores, splits,
cobertura, reglas y referencias de tratamiento, diagnóstico por bloque, seis
casos auditados de train, versiones y hashes de insumos, código y CSV.
Este bundle no contiene el modelo; se distribuye por separado (ver `modelo_ief.md`).
Las referencias estadísticas de diagnóstico están
ajustadas exclusivamente con train y persistidas dentro de `tratamiento`.

Desde la raíz del proyecto:

```bash
python ml/ief.py
python -m unittest docs.validar_ief -q
```

Un destino existente se acepta solo si ambos archivos son idénticos. Para
reproducir en otro entorno o destino:

```bash
python ml/ief.py --output-dir reproduccion_ief/matriz
```

La publicación es atómica por carpeta. Un fallo no publica un bundle parcial;
un destino diferente ya existente no se sobrescribe. Las tablas y las capturas
no se modifican. No se realizan consultas de red ni se agregan dependencias.

`docs/validar_ief.py` cubre inflación nominal frente a crecimiento real, unidades
y puntos porcentuales, calentamiento, huecos, ceros, IPC ausente, situaciones
desconocidas, invariancia del pasado ante cambios futuros, claves, conservación
del universo, splits, integridad y publicación reproducible. Se ejecutan además
las suites de inflación, semántica y contrato relacional del proyecto.

Para el informe, esta matriz aporta la preparación de datos, definición de
variables y separación temporal de Metodología, y la cobertura de Resultados.
El desempeño del detector y su comparación con el baseline corresponden a la
siguiente etapa.


## Fundamento técnico

La transformación es una decisión de este protocolo, no una recomendación
específica de la biblioteca. El logaritmo natural se documenta en
[NumPy 2.3](https://numpy.org/doc/2.3/reference/generated/numpy.log.html).
[Isolation Forest 1.8](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.IsolationForest.html)
selecciona puntos de corte aleatorios dentro del rango de cada variable; por eso
una transformación no lineal puede modificar el resultado y debe evaluarse.
