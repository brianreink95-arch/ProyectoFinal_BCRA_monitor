# Features ICC — primera implementación

Versión de features **1.0**. Consumidor: baseline experimental hipotecario ya
implementado y futuro experimento PCA del ICC. No hay modelo, score productivo
ni clasificación de regímenes. Las features y su CSV original no se modificaron.
Implementación: [ml/features.py](../ml/features.py).

## Alcance y decisiones frente al plan

El plan permite `mes × segmento` **o un agregado definido**. Se comienza por
**hipotecarios en moneda local a personas humanas**, no por un supuesto total
nacional construido sumando stocks pendientes de validación absoluta. Es un
primer componente segmentado del ICC, no representa todo el crédito argentino.
Permite observar crédito, condiciones de tasa, composición y momentum/volatilidad
con seis features y sin sumar ML con ME ni poblaciones solapadas.

La tasa hipotecaria UVA es un **proxy parcial** de condiciones: no es la tasa
promedio del universo hipotecario ML. La metodología guardada describe una tasa
ponderada por **montos otorgados al sector privado**, mientras 927 mide **saldos
vigentes de personas humanas**: distinta población, modalidad y stock frente a
otorgamientos. Son medidas complementarias, no una tasa implícita del stock.
La composición usa destinos del mismo agregado, cuya coherencia interna puede comprobarse. No se afirma que todas las
series del catálogo estén listas para construir un índice general.

Las referencias en documentos anteriores a features como “próxima etapa” eran
el estado previo, no modelos existentes. La propuesta sigue siendo alcance.
Se mantiene el bloqueo de sumas de niveles absolutos del plan: aquí no se crea
ningún nuevo stock. La única suma se usa en memoria para reconciliar el desglose
con el total publicado. No se exporta una tabla auxiliar ni se cambia el catálogo.

## Unidad, clave y tiempo

Una fila es un **mes de referencia del agregado hipotecario ML a personas humanas**.
PK: `(fecha_mes, segmento)`, con `fecha_mes` al cierre de mes y
`segmento = Hipotecarios ML a personas humanas`.

- Grilla continua desde el primer hasta el último mes de las series seleccionadas.
  Se reinsertan todos los huecos antes de calcular rezagos; no se desplazan filas
  después de quitar nulos. En esta corrida: diciembre de 1999 a agosto de 2026.
- `cutoff_referencia = fecha_mes`: solo se usan referencias de ese mes y anteriores.
  Una referencia mensual debe estar fechada al cierre y ser única por serie-mes.
- `ultima_referencia_a` es el máximo de referencias de toda A (2026-09-10), **no**
  fecha de publicación. No se extiende la grilla a septiembre, donde ninguna de
  estas siete series tiene observación. Julio y agosto sí permanecen aunque falte stock.
- `consolidacion_utc` indica transformación, no adquisición ni disponibilidad
  original. `disponibilidad_historica_verificada=False` en todas las filas.
  No se inventa una fecha de disponibilidad: no hay vintages/publicaciones verificadas.
  Esta matriz solo habilita evaluación **retrospectiva por período**, no point-in-time.

## Series seleccionadas y calidad

Todas provienen de `base_a/series.csv` y `base_a/observaciones.csv` de la misma
consolidación. Son mensuales (`M`, `observacion_mensual`): se conserva la única
observación, sin medias entre meses ni arrastre. **No se incorporan tasas diarias**;
por ello no se necesita aceptar ni imputar un mes diario abierto.

| ID | Serie | Unidad publicada / moneda | Motivo y cobertura observada |
|---|---|---|---|
| 927 | Hipotecarios a personas humanas | Miles de ARS / ML | Agregado publicado, sin sumar líneas; 319 meses consecutivos, 1999-12–2026-06, positivos y sin nulos. Base de cambios nominales. |
| 1240 | Tasa de préstamos hipotecarios UVA | Porcentaje nominal anual / ML; tasa sobre UVA | Condiciones del financiamiento habitacional indexado, no costo total. 124 meses consecutivos, 2016-05–2026-08, sin nulos. No mezcla modalidades de tasa. |
| 1145 | Hipotecarios PH para construcción | Miles de ARS / ML | Destino asociado a construcción de vivienda dentro del mismo agregado; 319 meses, misma cobertura que 927. Numerador de composición. |
| 1146–1149 | Refacción, compra nueva, compra usada, otras operaciones | Miles de ARS / ML | Solo validadores del desglose del agregado: evitan calcular una participación sobre categorías incompatibles. No son cuatro predictores adicionales. |

El contrato mantiene `pendiente_escala_absoluta` para los stocks: no se corrige
ni se certifica esa escala. Se verificaron calendario completo, valores positivos,
unidad constante declarada y reconciliación en los 319 meses (máxima diferencia:
**2 unidades del valor almacenado**). Es evidencia de coherencia interna, no
prueba de ausencia de revisiones o cambios metodológicos.

La [metodología guardada](../data_a/metadata/bcra_monetarias_metodologia.csv)
indica que el BCRA puede repetir el último saldo conocido cuando falta información
contemporánea. `stock_observado=True` significa **observación publicada presente**,
no que todos los componentes estén actualizados ni que exista movimiento genuino.
No hay identificación por mes/entidad de esos arrastres. Tampoco puede inferirse
que un saldo repetido fue arrastrado: podría ser un saldo efectivamente constante.
No se modifica ni imputa el dato; en el baseline se declara
`contemporaneidad_stock_verificada=False` para todas las filas.

**Supuesto explícito:** los cambios relativos de 927 usan una escala multiplicativa
constante entre los meses de cada ventana; las participaciones usan una escala
común entre 1145 y 927. Ambas cancelan ese factor sin requerir conocer el nivel
absoluto. Debe revisarse este supuesto si cambian unidades, precisión o metodología.
La validación rechaza cambios de concepto, moneda, frecuencia, agregación y
precisión entera observada; no detecta por sí sola una redenominación histórica
no declarada en las fuentes.

No se eligen stocks ME, totales de prestatarios, tasas de tarjetas con huecos,
TAMAR con cambio metodológico, inflación para improvisar un deflactor, ni la
cotización aislada. B queda pendiente de historia suficiente; IAP e IEF no se
implementan. La excepción 1199 se verifica en la entrada completa de A, pero esa
serie no participa: se preservan sus ceros originales y nulos analíticos pre-1993-06.

## Diccionario de features

Sea $S_t$ el valor analítico de 927, $C_t$ el de 1145, $r_t$ el de 1240 y
$g_t=100(S_t/S_{t-1}-1)$. Todas las features tienen frecuencia mensual.

| Feature | Significado y fórmula | Unidad | Ventana y mínimo | Interpretación / dirección esperada |
|---|---|---|---|---|
| `credito_var_nominal_1m_pct` | Variación del stock nominal: $100(S_t/S_{t-1}-1)$ | % mensual | 2 stocks válidos consecutivos; denominador positivo | Mayor variación señala expansión **nominal**; incluye indexación/revaluación, no crédito nuevo ni crecimiento real. |
| `credito_var_nominal_3m_pct` | Momentum acumulado: $100(S_t/S_{t-3}-1)$ | % en 3 meses, sin anualizar | 4 stocks válidos consecutivos, no solo extremos; denominador positivo | Mayor expansión nominal reciente; no es media de tres variaciones ni suma de porcentajes. |
| `tasa_uva_tna_pct` | Nivel de la TNA sobre UVA: $r_t$ | % nominal anual **sobre capital indexado** | 1 observación mensual no negativa | Mayor tasa puede indicar condiciones más restrictivas, ceteris paribus. No es CFTEA, TEA ni costo total nominal en pesos. |
| `tasa_uva_delta_3m_pp` | Cambio de la tasa: $r_t-r_{t-3}$ | Puntos porcentuales de TNA | 4 tasas válidas consecutivas | Aumento implica encarecimiento relativo de esta modalidad; se expresa en pp, no en % de crecimiento. |
| `participacion_construccion_pct` | Composición por destino: $100 C_t/S_t$ | % del stock hipotecario ML PH | Total positivo y 5 componentes válidos, no negativos y reconciliados en el mes | Mayor peso de construcción frente a otros destinos. **Sin signo monotónico expansión/restricción**: no asignar peso positivo por defecto en el baseline. |
| `credito_volatilidad_6m_pp` | Dispersión de cambios nominales recientes: desviación estándar poblacional de $g_{t-5},\ldots,g_t$, `ddof=0` | Puntos porcentuales de variación mensual | 6 variaciones válidas consecutivas, que requieren 7 stocks de calendario | Mayor valor significa inestabilidad, no necesariamente restricción; un auge también puede elevarla. Sin orientación de score automática. |

La volatilidad es:

$$
\sigma_{6,t}=\sqrt{\frac{1}{6}\sum_{j=0}^{5}(g_{t-j}-\bar g_{6,t})^2},
\qquad \bar g_{6,t}=\frac{1}{6}\sum_{j=0}^{5}g_{t-j}.
$$

Se dejan fuera crecimiento a 12 meses, tendencias adicionales y múltiples tasas
altamente solapadas para mantener la primera matriz pequeña. El baseline posterior
compara combinaciones de crecimiento y tasa, con pesos por dimensión.
Composición y volatilidad siguen como **descriptores con peso cero**, no se borran:
no hay fundamento para orientarlas automáticamente como expansión/restricción.

## Nulos, controles y elegibilidad

- No imputar, interpolar, completar con cero ni forward-fill. No ajustar scalers,
  PCA, imputadores, modelos ni percentiles. No winsorizar ni eliminar extremos.
- Stock cero reportado sigue siendo cero: puede producir -100% con denominador
  anterior positivo. Un denominador cero/nulo/negativo produce feature nula,
  **nunca infinito**. Stock negativo es inválido para estas features.
- Tasa cero es válida; tasa negativa se considera inválida en este primer contrato
  económico y se marca. Un hueco intermedio invalida el cambio a 3 meses incluso
  si ambos extremos están observados.
- Composición: se necesitan los cinco destinos observados y no negativos;
  ninguno puede superar el total. Se exige
  $|\sum_{i=1145}^{1149}X_{i,t}-S_t|\leq3$ en valores almacenados.
  **Supuesto de redondeo:** cinco componentes y total publicados enteros, cada
  uno redondeado con error máximo de 0,5; tolerancia conservadora $6\times0,5$.
  El catálogo no certifica esa política de redondeo; es una regla inicial explícita
  apoyada por la diferencia máxima observada de 2. Si cambia la precisión, la CLI
  exige revisar la regla. No se ajustan los componentes para que sumen el total.
- Una feature calculable se conserva aunque otra no lo sea. `elegible_icc=True`
  exige **las seis features**, sin recortar las filas no elegibles. No define
  todavía pertenencia a train, validación o test.
- `stock_observado`, `tasa_observada`, `desglose_completo` y
  `composicion_consistente` permiten explicar cobertura. Los conteos
  `n_meses_stock_4m`, `n_meses_tasa_4m`, `n_variaciones_6m` son controles,
  no predictores. Cada feature tiene `motivo_<feature>`: vacío si está disponible;
  en otro caso identifica stock/tasa ausente o inválido, ventana incompleta,
  denominador no positivo, desglose ausente/inválido o no reconciliado.
- `n_features_disponibles` y `motivos_no_elegible` resumen el diagnóstico por fila.
  La ausencia anterior al inicio de una serie y la posterior a su último dato
  no se confunden con un saldo cero. La documentación de cobertura distingue sus causas.

### Períodos utilizables de esta consolidación

**321 filas**, 1999-12–2026-08; **119 elegibles consecutivas**, 2016-08–2026-06;
**202 no elegibles conservadas**. Antes de mayo de 2016 no hay tasa UVA; mayo–julio
no completan su ventana de 3 meses. Julio–agosto de 2026 no tienen stock ni
desglose. Los primeros meses del stock tampoco completan sus rezagos/volatilidad.

Esto es elegibilidad técnica de un experimento retrospectivo, no suficiencia
estadística ni validación económica del índice. Los 119 meses no son observaciones
independientes; no dividir aleatoriamente las filas.

## Origen, salida y ejecución

Origen verificado: `data_analytics/latest.json` → consolidación
**20261005_011327_837742**, estado `completed`, ABC e insumos intactos.
Transformada a `2026-10-05T01:13:27.837742+00:00` (4 de octubre en Argentina);
fuentes adquiridas en septiembre, no una extracción nueva de octubre.

Salida única: [icc.csv](../data_analytics/features/20261005_011327_837742/icc.csv).
Regla de ubicación: `data_analytics/features/<run_origen>/icc.csv`, fuera de las
12 tablas relacionales. La repetición reemplaza atómicamente **el mismo CSV**;
no crea copias, pivots ni metadata duplicada. Una futura consolidación tiene
su propia matriz, sin concatenar corridas.

Desde la raíz, con el entorno instalado:

```bash
python ml/features.py
python -m unittest docs.validar_features_icc docs.validar_semantica docs.validar_relacional -v
```

En PowerShell con el entorno local:

```powershell
& '.\.venv\Scripts\python.exe' 'ml\features.py'
& '.\.venv\Scripts\python.exe' -m unittest docs.validar_features_icc docs.validar_semantica docs.validar_relacional -v
```

La CLI no tiene opción de extracción; `--root` permite indicar la raíz del
proyecto. No importa los pipelines ni consulta APIs. Usa lectura/exportación
de `lib/common.py` y validación de `lib/relacional.py`. Rechaza puntero parcial,
corrida incompleta, modificación de tablas A respecto de sus SHA-256 o cambio
del contrato desde la consolidación. La dimensión de series versionada es el
catálogo aplicado a esos datos, no un catálogo posterior.

El CSV incluye `run_origen`, `version_features`, hashes de las dos tablas A,
contrato, catálogo de origen y código de features, además de fechas y controles.
No incorpora un timestamp de ejecución que rompa reproducibilidad. Los hashes
permiten identificar versiones; el entorno se registra en la consolidación.
IDs, fechas, hashes, banderas y motivos **no** son features del futuro modelo;
la lista explícita `FEATURES_ICC` es la única selección de seis predictores.
Al releer el CSV, preservar fechas, IDs, hashes, versión (incluido `1.0`) y motivos
como texto; los motivos vacíos significan ausencia de problema, mientras que
las features numéricas vacías representan nulos. No confiar en la inferencia
numérica de pandas para `version_features`.

## Evidencia y límites antes de entrenamiento

Se ejecutó la CLI dos veces y se comprobó igualdad byte a byte por SHA-256.
Las pruebas cubren PK, orden/continuidad mensual, ventanas, huecos, ceros,
redondeo/reconciliación, tasas inválidas, cambios de catálogo, excepción 1199,
rechazo de corridas incompletas/tablas alteradas, no uso de futuro, reproducibilidad
y fuentes intactas. No se escribió en las fuentes ni se ejecutó adquisición.

Ejemplo real **junio de 2026**, comprobado directamente contra observaciones:

- Stock: mayo 6.728.825; junio 6.943.415 → variación **3,189115%**.
- Marzo 6.400.004 → variación a 3 meses **8,490792%**.
- TNA UVA: marzo 6,37; junio 7,02 → nivel **7,02%**, cambio **0,65 pp**.
- Construcción junio 384.720 → participación **5,540789%**.
- Seis cambios mensuales enero–junio (siete stocks diciembre–junio) →
  volatilidad **0,874726 pp**, con `ddof=0`.

Los valores de stock anteriores son números almacenados, no una certificación
nueva de sus niveles absolutos. El mayor salto mensual histórico de 927 es
**291,54% en 2002-01**: se conserva sin atribuirlo automáticamente a una causa
ni llamarlo expansión real. Ese mes no es elegible por falta de tasa UVA.
Antes de ampliar la historia utilizable debe auditarse su metodología/escala.

Los splits y el baseline train-only ya se implementaron según el protocolo
siguiente. Antes de entrenamiento siguen pendientes: resolver o acotar la causa
de los extremos, revisar saturación y representatividad de train, justificar el
constructo económico del agregado/proxy, definir evaluación expansiva de modelos
y asegurar un test realmente no inspeccionado. Escala/vintages siguen bloqueando
ampliaciones y validación point-in-time. `ml/train.py`, `ml/score.py`, IAP e IEF
siguen pendientes.

## Splits y baseline experimental hipotecario — versión 1.0

Implementación: [ml/baseline.py](../ml/baseline.py). Referencia para comparar con
el futuro modelo, **no un ICC nacional ni score productivo validado**. Consume el
CSV ICC existente y lo contrasta con fuentes, fórmulas y código; no publica otra
matriz de features. Verifica el hash de metodología contra la misma consolidación.
No añade dependencias ni ejecuta adquisición.

### Protocolo temporal congelado

| Rol | Meses de calendario | Meses elegibles actuales | Uso |
|---|---|---|---|
| Train | 2016-08–2021-12 | 65 | Única población de ajuste de referencias empíricas. Mínimo inicial: 60 meses, aproximadamente cinco ciclos anuales; no garantiza suficiencia para un modelo. |
| Validación | 2022-01–2023-12 | 24 | Comparación descriptiva de variantes predefinidas; sin reajustar referencias ni pesos. |
| Evaluación retrospectiva | 2024-01–2026-06 | 30 | Valores experimentales con referencias congeladas; datos ya inspeccionados, **no test final intacto**. No se usan para escoger variante ni recalibrar. |
| Reserva posterior | Desde 2026-07 | 0 elegibles hoy | Sin puntuar, aunque una futura matriz tenga features completas. Un test genuinamente no inspeccionado sigue pendiente. |

Los cortes son por calendario, no porcentajes de filas ni umbrales de extremos.
Todas las variantes usan exactamente las mismas filas con seis features elegibles;
no se borran huecos ni se desplazan fronteras si falta un mes. Julio/agosto de 2026
ya tienen tasa conocida: “reserva posterior” no significa que ninguna variable
haya sido vista ni que esos meses sean futuros respecto de la fecha actual.

Las ventanas pueden usar contexto previo al inicio de un bloque: solo referencias
anteriores/al mes de la fila, sin targets futuros. No se necesita embargo de target
aquí; cuando haya uno debe definirse su horizonte. Los meses están autocorrelacionados.
El mapeo de percentiles de las filas de train usa todo train: es una transformación
in-sample retrospectiva, no un índice que hubiera estado disponible en cada fecha.

### Referencias y versiones comparables

Para cada predictor $x$, guardar los valores elegibles de train ordenados:

$$
P_T(x)=100\frac{\#\{x_i<x\}+0.5\#\{x_i=x\}}{n_T}.
$$

Los empates tienen rango medio; una referencia constante asigna 50 a su valor,
0 por debajo y 100 por encima. El mapa queda fijo: no se actualiza con validación,
evaluación retrospectiva ni reserva. Los nulos no se imputan. Valores fuera del
rango de train llegan a 0/100 sin recortar el dato original ni medir su magnitud.

Sea $p_1=P_T(g_{1m})$, $p_3=P_T(g_{3m})$, $p_r=P_T(r)$ y
$p_\Delta=P_T(\Delta_{3m}r)$:

| Referencia experimental | Fórmula | Propósito |
|---|---|---|
| `referencia_trimestral` | $0.5p_3+0.5(100-p_r)$ | Ancla predefinida: momentum nominal trimestral y condiciones de tasa UVA. |
| `referencia_mensual` | $0.5p_1+0.5(100-p_r)$ | Sensibilidad a horizonte más corto, sin decidir su superioridad por correlación. |
| `referencia_balanceada` | $0.25[p_1+p_3+(100-p_r)+(100-p_\Delta)]$ | Comparar crecimiento mensual/trimestral y nivel/cambio de tasa; stock mantiene 50% del peso total, no 2/3 por aportar dos columnas. |

Las tres referencias están en 0–100, **sin regímenes ni calibración productiva**.
Mayor crecimiento nominal y menor tasa/cambio de tasa las elevan como hipótesis
ceteris paribus, no como evidencia de bienestar, crédito real o ausencia de riesgo.
No hay una variante declarada ganadora ni pesos optimizados. Composición y
volatilidad se conservan para explicar el período, **no entran en ninguna fórmula**.

### Redundancia y sensibilidad comprobadas

Las observaciones del usuario se reproducen: Pearson en 119 meses es 0,9354 entre
crecimientos; volatilidad correlaciona 0,8416/0,8448 con ellos. Eso es diagnóstico
retrospectivo, no criterio de selección ajustado sobre todos los datos. En train,
crecimientos correlacionan **0,9674** y volatilidad **0,6881/0,7014**.
El artefacto guarda Pearson/Spearman de las seis features **solo de train**.

En los 24 meses de validación, frente a la referencia trimestral:

| Variante | Diferencia absoluta media | Máxima | Correlación entre referencias |
|---|---|---|---|
| Mensual | 6,12 pp | 39,23 pp | 0,8849 |
| Balanceada | 8,82 pp | 25,38 pp | 0,8767 |

La redundancia no vuelve intercambiables todas las versiones. **18/24 tasas UVA**
están fuera del rango de train, igual que 1/24 crecimientos mensuales y 3/24 cambios
de tasa. La saturación advierte cambio de distribución y limita discriminación;
no se resuelve ajustando percentiles con validación/test. Requiere revisar el
protocolo de ventanas expansivas antes de un modelo, sin cambiar el test para
obtener mejores resultados. No se reportan accuracy ni métricas sin etiqueta.

### Extremos dentro de la muestra elegible

| Mes | Evidencia verificada | Estado |
|---|---|---|
| 2024-02 | TNA UVA 0,20% | Fuente coincide; puede reflejar condiciones/composición de otorgamientos, no se conoce la causa. |
| 2024-10 | Stock 510.345 → 740.414; variación 45,0811% | Destinos aumentan y reconcilian (diferencia de redondeo 1). No identifica desembolsos nuevos ni descarta actualización/arrastre o cambios metodológicos. |
| 2024-11 | Stock 955.895 frente a 376.691 de agosto; variación a 3 meses 153,7610% | Fórmula y fuente coinciden; causa económica/metodológica pendiente. |

La descripción metodológica conservada es general; no hay vintages, flags de
actualización por entidad ni desglose de otorgamientos que permitan atribuir
estos movimientos. No se eliminan, winsorizan ni normalizan automáticamente.
Los tres casos se registran como revisión **ex post**, no como features, targets
ni reglas de exclusión. La reserva posterior no se puntúa para fabricar evidencia
fuera de muestra.

### Outputs, consumidores y ejecución

Dentro de `data_analytics/baselines/<run_origen>/` se publican únicamente:

- `icc_hipotecario.csv`: misma PK mensual, split, motivos de exclusión, percentiles,
  tres referencias y diferencias, composición/volatilidad descriptivas y banderas
  de disponibilidad/contemporaneidad no verificadas. Consumidor: comparación e
  interpretación académica frente al futuro modelo.
- `protocolo_icc.json`: fechas, población de ajuste, valores train ordenados,
  pesos/direcciones, hashes, entorno, diagnósticos train/validación y revisión de
  extremos. Consumidor: reproducir exactamente la referencia y los splits del
  futuro entrenamiento. Es un artefacto de ajuste, no una nueva configuración.

El JSON se publica al final y contiene el hash del CSV; ante una publicación
interrumpida no debe consumirse una pareja cuyo hash no coincida. La repetición
reemplaza los mismos archivos; no crea copias ni modifica features, fuentes,
latest o las 12 tablas. Preservar versiones y metadatos como texto al releer CSV.

```powershell
& '.\.venv\Scripts\python.exe' 'ml\baseline.py'
& '.\.venv\Scripts\python.exe' -m unittest docs.validar_baseline_icc -v
```

En otros entornos: `python ml/baseline.py`. Las pruebas verifican calendario,
empates, ceros/nulos, mínimo train, pesos, invariancia del ajuste ante cambios de
validación/evaluación/reserva, descriptores sin peso, integridad de insumos,
relectura/exportación y reproducibilidad. No se entrenó PCA ni se implementó
scoring, IAP o IEF.
