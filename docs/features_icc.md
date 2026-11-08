# Features ICC — registro de candidatas

Features 3.0; revisión del protocolo 3.1 — 6 de octubre de 2026 (Buenos Aires).

Ubicación: `docs/features_icc.md`. Implementación: `ml/features.py`.
Criterios económicos: [criterios_datos.md](criterios_datos.md).
Secuencia de modelos: [plan_ml.md](plan_ml.md).

## Qué está implementado

Una matriz mensual retrospectiva del agregado **hipotecarios en moneda local a
personas humanas**, con 14 features candidatas, disponibilidad por variable y
procedencia. No es un ICC nacional, un modelo entrenado ni una medida directa de
acceso. El contrato relacional sigue en **2.0 y 13 tablas**; 3.0 es la versión de
features. No se agregan extracciones, fuentes ni tablas relacionales.

El stock mide **saldo vigente**, no cantidad de personas, oferta disponible ni
nuevos desembolsos. Su nivel y dinámica aportan evidencia de volumen crediticio;
no prueban accesibilidad para una persona de clase media. Una tasa baja con
muy poco stock no basta para declarar favorable el contexto. Con stock real
igual, una tasa menor mejora la dimensión de costo, sin demostrar mayor acceso.
El piloto combina y calibra volumen, costo y momentum mediante S1 4.0.
La matriz de candidatas sigue siendo un artefacto separado del índice.

## Fuentes y preparación

| Serie | Concepto | Uso implementado |
|---|---|---|
| 927 | Saldo hipotecario ML de personas humanas | Nivel, crecimiento, cambio absoluto, aceleración y volatilidad reales; denominador de participaciones. |
| 1145 | Construcción | Participación por destino. |
| 1146 | Refacción | Participación por destino. |
| 1147 | Compra de viviendas nuevas | Participación por destino. |
| 1148 | Compra de viviendas usadas | Participación por destino. |
| 1149 | Otras | Participación por destino. |
| 1240 | TNA de préstamos UVA al sector privado | Nivel y cambio de tasa; proxy parcial de costo. |
| `deflactor_ipc` | IPC nacional INDEC, nivel general | Stocks a precios de diciembre de 2016. |

Base B no aporta al ICC actual: sus snapshots no tienen historia coincidente
con la ventana elegible actual y quedan para IAP. No se añade un contador de
acceso, ingreso, deudores o desembolsos que las tablas seleccionadas no contienen.
No se incorpora otra serie del catálogo sin validar concepto, unidad y consumidor.

Los seis stocks fueron contrastados con XLS oficiales: su escala numérica es
**millones de ARS**, aunque el metadato original de la API declara miles.
Se preserva ese metadato; el cálculo exige `unidad_validada=millones_ARS` y
validación oficial por mes. Cada importe ajustado requiere estado `ajustado`.
Los nominales históricos quedan intactos. No se usa el empalme exploratorio
anterior a diciembre de 2016 como deflactor del dataset ML.

Sea `R_t` el stock 927 en millones de pesos de diciembre de 2016:
`R_t = nominal_t * 100 / IPC_t`. Sea `r_t` la TNA UVA en porcentaje anual y
`g_k(t) = 100 * (R_t / R_(t-k) - 1)`.
Las tasas no se dividen por IPC: la TNA sobre UVA no es tasa fija en pesos,
costo financiero total ni tasa real calculada con inflación.

## Diccionario de las 14 candidatas

Todas las ventanas terminan en el mes de la fila. Los conteos de stocks incluyen
los extremos; no se comprime el calendario antes de desplazar valores.

| Feature | Fórmula | Unidad | Historia necesaria |
|---|---|---|---|
| `credito_stock_real_millones_ars_dic2016` | `R_t` | Millones ARS dic. 2016 | Stock actual validado, cero incluido. |
| `credito_var_real_1m_pct` | `g_1(t)` | % | 2 stocks consecutivos; denominador positivo. |
| `credito_var_real_3m_pct` | `g_3(t)` | % | 4 stocks consecutivos; denominador positivo. |
| `credito_var_real_12m_pct` | `g_12(t)` | % | 13 stocks consecutivos; denominador positivo. |
| `credito_delta_real_3m_millones_ars_dic2016` | `R_t - R_(t-3)` | Millones ARS dic. 2016 | 4 stocks consecutivos; ceros permitidos. |
| `credito_aceleracion_real_3m_pp` | `g_3(t) - g_3(t-3)` | pp | 7 stocks consecutivos; denominadores `t-3` y `t-6` positivos. |
| `credito_volatilidad_real_6m_pp` | Desvío estándar poblacional (`ddof=0`) de los últimos 6 `g_1` | pp | 6 cambios válidos; 7 stocks consecutivos. |
| `tasa_uva_tna_pct` | `r_t` | % nominal anual sobre UVA | Tasa actual no negativa. |
| `tasa_uva_delta_3m_pp` | `r_t - r_(t-3)` | pp | 4 tasas mensuales consecutivas. |
| `participacion_construccion_pct` | `100 * 1145_t / 927_t` | % | Total positivo y cinco destinos reconciliados. |
| `participacion_refaccion_pct` | `100 * 1146_t / 927_t` | % | Ídem. |
| `participacion_compra_nuevas_pct` | `100 * 1147_t / 927_t` | % | Ídem. |
| `participacion_compra_usadas_pct` | `100 * 1148_t / 927_t` | % | Ídem. |
| `participacion_otras_pct` | `100 * 1149_t / 927_t` | % | Ídem. |

Las participaciones usan nominales del mismo mes: el factor IPC común se cancela.
El desglose exige cinco valores no negativos, cada uno menor o igual al total y
una diferencia absoluta entre suma y total de hasta **3 unidades publicadas**,
por el redondeo a enteros de seis valores. No se suma ese desglose a 927.
Por redondeo las participaciones pueden no sumar exactamente 100; no se las
renormaliza. Cada variable conserva su motivo si no puede calcularse.

**Interpretación para explorar, todavía sin pesos:** nivel y cambio absoluto
ayudan a distinguir un rebote porcentual sobre base pequeña de una expansión
con más volumen. Crecimiento anual aporta una comparación menos dependiente
del último mes; aceleración compara dos trimestres contiguos. Volatilidad y
composición son descriptores: no se presupone que más volatilidad, construcción
u otro destino sea favorable. Los cinco porcentajes están casi restringidos por
su suma y los horizontes de crecimiento pueden ser redundantes; no deben entrar
automáticamente todos juntos a PCA o a un modelo.

No se define por ahora un cociente `stock/tasa`, un producto de percentiles,
un umbral de stock bajo ni una referencia normalizada de volumen. Elegirlos
requiere justificar su comportamiento y ajustar sus parámetros únicamente en
train. Una fórmula aditiva antigua no satisface por sí sola el criterio de
volumen y costo acordado.

## Disponibilidad y elegibilidad por consumidor

`FEATURES_ICC` registra candidatas calculadas; **no selecciona predictores**.
`elegibilidad_features(frame, requeridas)` exige una lista explícita y devuelve
máscara y motivos solo para esa lista, sin recortar filas ni imputar.

| Campo/perfil | Variables exigidas | Uso |
|---|---|---|
| `n_features_disponibles` | Conteo de las 14 disponibles | Diagnóstico por mes. |
| `candidatas_completas` | Las 14 | Cobertura conjunta; no requisito global de entrenamiento. |
| `elegible_comparacion_2_0` | Las seis de 2.0 | Reproducir la muestra y los valores anteriores. |
| `elegible_baseline_historico` | Crecimiento real 1/3m, TNA UVA y cambio de tasa 3m | Diagnóstico de la especificación aditiva antigua; no aprobación del nuevo ICC. |
| `elegible_icc` | Alias de `elegible_comparacion_2_0` | Compatibilidad temporal; no elegibilidad del futuro modelo. |

`motivo_<feature>` explica cada ausencia. `motivos_features_no_disponibles`
agrega las ausencias entre las 14; `motivos_no_elegible_<perfil>` agrega solo
las que afectan a ese perfil. `motivos_no_elegible` es alias de comparación 2.0.
Se conserva `n_features_disponibles_2_0` para comparar el conteo anterior.
Los controles de ventanas incluyen `n_meses_stock_real_4m/7m/13m`,
`n_meses_tasa_4m` y `n_variaciones_reales_6m`.

Un stock cero observado sigue siendo cero; permite nivel y cambio absoluto.
Un denominador cero impide variaciones porcentuales. Un dato ausente, negativo,
sin IPC o sin auditoría de unidad no se sustituye con cero ni con un nominal.
No se saltan huecos, se arrastra información ni se eliminan extremos.
La composición puede calcularse sin IPC porque compara nominales del mismo
mes; eso no habilita señales de stock real.

## Cobertura validada y protocolo temporal

Validación local sobre la consolidación disponible `20261005_232225_036387`,
contrato 2.0, IPC diciembre 2016–agosto 2026. No es una ejecución de la corrida
posterior informada por el usuario `20261005_233718_822781`.
La raíz usada tiene 321 filas mensuales (diciembre 1999–agosto 2026), 115 stocks
reales válidos (diciembre 2016–junio 2026) y 124 tasas (mayo 2016–agosto 2026).

| Cobertura | Meses | Primera fecha | Última fecha |
|---|---|---|---|
| Comparación 2.0: seis variables | 109 | 2017-06-30 | 2026-06-30 |
| Diagnóstico histórico: cuatro predictores | 112 | 2017-03-31 | 2026-06-30 |
| Todas las 14 candidatas | 103 | 2017-12-31 | 2026-06-30 |

El crecimiento anual comienza en diciembre de 2017; el nivel en diciembre de
2016; cambio absoluto trimestral en marzo de 2017 y aceleración en junio de 2017.
Los nuevos datos pueden cambiar estas coberturas. La matriz conserva también
meses parciales y sus motivos para que la selección posterior determine su muestra.

| Bloque de calendario acordado, protocolo 3.1 | Comparación 2.0 | Diagnóstico de cuatro predictores | Todas las 14 |
|---|---|---|---|
| Train: agosto 2016–febrero 2022 | 57 | 60 | 51 |
| Validación: marzo 2022–diciembre 2023 | 22 | 22 | 22 |
| Evaluación retrospectiva: enero 2024–junio 2026 | 30 | 30 | 30 |

El 6 de octubre de 2026 se aprobó explícitamente extender train dos meses:
enero y febrero de 2022. La validación comienza en marzo para evitar solapamiento;
la retrospectiva y reserva no cambian. La decisión se registra como D21 en
`criterios_datos.md`. No se cambia el mínimo de **60** ni se aplica shuffle.

El diagnóstico de cuatro predictores pasa de 58 a **60** meses y cumple el mínimo.
El perfil comparable de seis pasa de 55 a **57**; todas las 14 juntas, de 49 a
**51**. El índice futuro puede tener otra muestra según la selección aprobada:
60 es el conteo del perfil diagnóstico, no una garantía para cualquier modelo.

D22 adopta el paquete S1 completo. El perfil del índice 4.0 exige **R/g3/r**:
stock real, crecimiento trimestral y TNA UVA. Tiene60 train,22 validación y30
retrospectiva en esta corrida. El antiguo flag de cuatro predictores conserva
su significado histórico; no determina la elegibilidad del consumidor S1.
Baseline S1 implementado; PCA entrenado y rechazado por reconstrucción.
La fórmula y todos los controles están en `criterios_datos.md`, sección9.

Los datos 2024–2026 ya se inspeccionaron y no son un test final intacto. La
reserva desde julio de 2026 no se puntúa; algunas tasas ya son conocidas.
No hay shuffle. Ventanas y variables usan referencias anteriores o del mismo
mes, pero no se dispone de vintages para certificar qué se conocía entonces.
`disponibilidad_historica_verificada=False` conserva esa limitación.

## Ejemplo comprobado — junio de 2026

Stock real marzo: 57.777,0955; mayo: 57.970,1626; junio: 58.711,0951 millones de
ARS de diciembre de 2016. Crecimiento real mensual **1,278127%**, trimestral
**1,616557%**. TNA UVA junio **7,02%**, marzo **6,37%**: cambio **+0,65 pp**.
Participación construcción **5,540789%**; volatilidad mensual de seis cambios
**0,627357 pp**. La nueva generación conserva las seis features anteriores.

## Ejecución, persistencia y consumidores

Desde la raíz, después de copiar los cambios:

```bash
python ml/features.py
python ml/baseline.py --check-only
python -m unittest docs.validar_features_icc_v3 -v
```

Los dos scripts aceptan `--root <raiz_proyecto>` y operan sin red.
`features.py` solo deriva la matriz desde la consolidación vigente; no extrae ni
reconsolida. Si las tablas necesitan actualizarse, ejecutar antes el pipeline
habitual. `baseline.py --check-only` informa cobertura del core S1 sin calibrar.
Sin ese flag genera el baseline4.0; `train.py` evalúa PCA y `score.py` genera el índice
con el método admitido por el artefacto. Ver `../LEEME_ICC.md` para comandos.

Salida: `data_analytics/features/<run_origen>/v3.0/icc.csv`.
Se conserva el archivo anterior `features/<run_origen>/icc.csv` de 1.0/2.0.
Una repetición de 3.0 con la misma fuente y código reemplaza atómicamente el
mismo archivo con contenido idéntico; no crea duplicados por fecha de ejecución.
La procedencia incluye hashes de tablas, IPC, contrato, catálogo y código.
Los consumidores deben resolver la ruta con `ruta_matriz_icc` y seleccionar
sus columnas/requisitos explícitamente. No buscar la matriz anterior por defecto
ni interpretar `elegible_icc` como permiso para entrenar el nuevo índice.

Consumidores vigentes: diagnóstico de las14 candidatas y baseline/train/score S1
con requisitos explícitos R/g3/r. Outputs4.0 separados de la matriz3.0. Las demás
features son descriptores o sensibilidades; no se agregan las14 al modelo por
defecto. Los artefactos nominales históricos permanecen sin cambios.

## Consumidor adicional — análisis factorial 4.1

D23 conserva el core R/g3/r y su elegibilidad explícita, sin modificar las14
features3.0. `train.py --method factor_analysis` aprende el factor sobre los60
meses comunes y lo evalúa en22. `score.py` usa el modelo JSON explícito sin fit.
No se agregan series ni nuevas tablas. FA fue rechazado por representación de
volumen y reconstrucción; se conserva un factor diagnóstico, mientras el índice
sigue con baseline S1. Detalle en criterios §10 y `../LEEME_ICC.md`.

## Consumidor adicional — PCA2 diagnóstico 4.2

D24 conserva core R/g3/r, features3.0 y referencias S1. Se generan dos
proyecciones estadísticas en lugar de un score PCA2. El segundo eje recupera
información del nivel, pero la comparación de reconstrucción con V/H2D no pasa.
`icc_indice` conserva baseline S1. No hay mínimos de carga económica ni mapping
0–100 por PC individual. Definir un agregado de las dos PCs a favorabilidad
permanece pendiente. Criterios §11 y guía `../LEEME_ICC.md`.
