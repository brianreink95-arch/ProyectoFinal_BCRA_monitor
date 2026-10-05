# Plan de feature engineering, entrenamiento y scoring

Versión 1.2 — 4 de octubre de 2026 (Buenos Aires).

Fuente de objetivos: propuesta del Proyecto Final, secciones 9.1, 9.2 y 9.3.
Este documento distingue avance real y trabajo pendiente. **Las primeras features
ICC están implementadas; los modelos y los scores todavía no.** No hay targets,
etiquetas de default ni índices simulados presentados como resultados reales.

## Organización y secuencia de implementación

1. **Tablas relacionales — implementado.** Ejecutar `actualizar_bases.py` y validar
   las 12 tablas del contrato, referencias, cobertura y reconciliación.
2. **Feature engineering — ICC inicial implementado.** `ml/features.py` lee solo
   A de la consolidación ABC completa indicada por `data_analytics/latest.json`,
   aplica los tipos/PK/FK del contrato y verifica hashes. Publica una única matriz
   ICC con origen, cutoff de referencia, versión, hashes y elegibilidad; conserva
   filas excluidas y sus motivos. IAP/IEF y ampliaciones ICC siguen pendientes.
   El diccionario y las limitaciones están en [features_icc.md](features_icc.md).
3. **Baselines — ICC hipotecario experimental implementado.** `ml/baseline.py`
   consume la matriz persistida verificada, congela splits por calendario y
   ajusta referencias empíricas solo en train. Compara tres variantes con las
   mismas filas elegibles; guarda referencias/splits y diagnósticos train/validación.
   No entrena un modelo ni produce un score validado. Baselines IAP/IEF pendientes.
4. **Entrenamiento — posterior.** Implementar `ml/train.py` con preprocesamiento,
   modelo, configuración, semilla, métricas y versión de datos reproducibles.
5. **Scoring — posterior.** Implementar `ml/score.py` para aplicar artefactos ya
   ajustados, sin reentrenarlos, y producir las tres salidas de índices.

Estos nombres son el plan de archivos; no se crean scripts vacíos ni nuevas
dependencias ML hasta implementarlos. Mantener la extracción y transformación
de tablas en `base_a.py`, `base_b.py` y `base_c.py`.

Las matrices de features son datasets de entrenamiento derivados y versionados,
no nuevas dimensiones de la base relacional. Los scores sí serán resultados
con un consumidor definido en la web. No escribir archivos de scores si el
modelo no cumple sus criterios de validación.

## ICC — Condiciones Crediticias y Momentum

**Unidad:** mes y segmento (o agregado definido). **Fuentes:** A/series y
A/observaciones. B/snapshots y B/ofertas solo aportarán contexto de oferta en
las ventanas donde haya historia suficiente, sin recortar toda A al corto
solapamiento disponible.

**Avance real 1.0:** agregado `Hipotecarios ML a personas humanas`, no un ICC
nacional. Seis features: cambios nominales de 927 a 1/3 meses; nivel de TNA UVA
1240 y cambio a 3 meses; participación de construcción 1145/927; volatilidad de
seis cambios mensuales. El desglose 1145–1149 valida composición, no agrega
predictores. La tasa UVA es un proxy parcial del agregado, no su costo promedio.
No se suman stocks ML/ME ni se certifica su escala absoluta: los cocientes
suponen escala constante/común y se comprueba coherencia interna.

Salida `data_analytics/features/<run_origen>/icc.csv`, con PK
`(fecha_mes, segmento)`. Origen actual `20261005_011327_837742`: 321 filas
1999-12–2026-08, **119 elegibles consecutivas 2016-08–2026-06**, 202 excluidas
conservadas. No hay series diarias en esta selección; no se aceptan referencias
posteriores a cada fila ni se imputa. No hay disponibilidad histórica verificada.
Diccionario, reglas y ejemplos reales: [features_icc.md](features_icc.md).
Ejecutar `python ml/features.py`; validar con `python -m unittest docs.validar_features_icc -v`.

La tabla siguiente describe familias y ampliaciones previstas; no todas sus
ventanas/series están implementadas. Los splits y el baseline inicial ya existen;
antes de modelos revisar extremos, saturación y protocolo de estabilidad.
Composición y volatilidad quedan como descriptores con peso cero, sin dirección
automática. El stock publicado puede contener saldos arrastrados por BCRA;
`stock_observado=True` no certifica contemporaneidad. La tasa 1240 pondera
montos otorgados al sector privado, no saldos PH: no es la misma población.
No se eliminan extremos ni columnas por correlaciones observadas.

| Familia de features | Construcción inicial | Condición |
|---|---|---|
| Tasas | Media mensual de tasas diarias; nivel y cambio en puntos porcentuales a 1/3 meses. | Unidad y frecuencia del catálogo; mes completo. |
| Crédito | Variación nominal a 1/3/12 meses y tendencia a 3/6 meses, por segmento/línea. | Mismos conceptos y unidades; denominador válido; meses consecutivos. |
| Composición | Participaciones dentro de categorías comparables, sin sumar ML con ME sin regla explícita. | Evitar doble conteo y agregados solapados. |
| Momentum/volatilidad | Cambios y ventanas retrospectivas de variaciones, no de magnitudes incompatibles. | Historial completo requerido para cada ventana. |
| Oferta B, posterior | Número de prestadores y distribuciones de costos por familia/denominación/tasa. | Solo captura diaria completa, disponible al cutoff; no contar registros como productos únicos. |

Crear un registro de features con nombre, fórmula, unidad, series usadas,
ventana, mínimo de observaciones, tratamiento de nulos, cutoff y dirección
económica esperada. No asumir que toda tasa alta o todo stock alto expresa
expansión; definir la orientación de cada componente antes de ajustar el índice.

**Baseline implementado:** referencias experimentales con ECDF de rango medio
ajustada solo en train. Trimestral y mensual: 50% crecimiento nominal a 3 o 1
meses + 50% percentil inverso de TNA UVA. Variante balanceada: stock (media de
los percentiles a 1/3 meses) mantiene 50%, tasa (nivel/cambio inversos) 50%.
Composición y volatilidad se conservan con peso cero. No hay variante ganadora,
optimización de pesos, regímenes ni score productivo.

**Splits 1.0 congelados:** train 2016-08–2021-12 (65 meses, mínimo 60);
validación 2022–2023 (24); evaluación retrospectiva 2024–2026-06 (30).
Este bloque ya fue inspeccionado y **no es test final intacto**. Reserva posterior
desde 2026-07: no puntuar, ni siquiera al incorporar observaciones elegibles.
No se garantiza que todas sus variables sean desconocidas: julio/agosto ya tienen tasa.
Un test realmente no inspeccionado debe definirse antes del modelo.

Se publica un CSV de comparación y un JSON de splits, referencias train, pesos,
hashes y diagnósticos bajo `data_analytics/baselines/<run_origen>/`. Se conserva
la única matriz de features sin cambios. Usar `python ml/baseline.py`.
El [protocolo completo](features_icc.md) documenta redundancia, los tres extremos
2024 de causa pendiente y sensibilidad: 18/24 tasas de validación fuera del
rango train. No recalibrar sobre validación/test para resolver saturación.
**Primer modelo:** escalado + PCA; evaluar si el factor captura variación coherente
y estable. Orientar su signo con una referencia económica declarada, no con
el período de test. K-Means/GMM para regímenes son una segunda comparación, no
una etiqueta verdadera de expansión/restricción. HMM queda como alternativa
posterior si justifica su complejidad.

**Evaluación:** ventanas expansivas mensuales con test posterior por fechas;
estabilidad de cargas, sensibilidad a selección y ventanas, varianza explicada,
coherencia económica y comparación con baseline. No medir accuracy sin etiquetas
externas justificadas. Las fronteras de régimen y la transformación a 0–100 se
calibran en entrenamiento y permanecen fijas al evaluar.

**Bloqueos:** stocks de escala absoluta pendiente no sirven para sumas de nivel;
las variaciones relativas solo se habilitan tras comprobar consistencia temporal.
No hay deflactor contratado: no llamarlas crecimiento real. La cotización USD
aislada no habilita conversión histórica, momentum cambiario ni comparación real.

**Matriz inicial implementada:** una fila `(fecha_mes, segmento)` con seis features,
procedencia, banderas y motivos de exclusión. Los splits congelados se publican
en el artefacto de baseline, sin duplicar/reemplazar la matriz.
**Score previsto:** `(fecha_mes, segmento, version_modelo)` con
score 0–100, momentum y régimen si su definición se valida.

## IAP — Atractivo Relativo de Productos Financieros

**Unidad:** observación de oferta dentro de una captura. **Fuentes:** B/ofertas,
B/snapshots y B/entidades; A/series y observaciones para referencias de tasas
solo cuando su disponibilidad temporal se pueda establecer.

| Familia de features | Construcción inicial | Condición |
|---|---|---|
| Segmento comparable | Familia, denominación y tipo de tasa; destino/beneficiario cuando sean utilizables. | No mezclar monedas, modalidades o tarjetas y préstamos sin especificación. |
| Condiciones | Monto mínimo/máximo, plazo, ingreso mínimo, edad, antigüedad laboral, relaciones cuota/ingreso y monto/tasación. | Nulos con indicadores de ausencia; valores válidos; log1p solo en magnitudes no negativas. |
| Requisitos/disponibilidad | Antigüedad de información y banderas de campos ausentes. | El cutoff es la captura, no la fecha informada; revisar información futura o antigua. |
| Contexto, posterior | Tasa de referencia conocida y condiciones generales de A. | Join as-of verificado; nunca usar una publicación posterior al cutoff. |

**Objetivo y segmentación:** modelar CFTEA donde sea comparable y esté observado;
un modelo separado puede usar TEA cuando no haya CFTEA. Nunca mezclar ambos como
una única etiqueta, ni confundir TEA de financiación de tarjetas con adelanto.
Al modelar CFTEA, excluir TEA/CFTEA y otras variables que sean componentes o
derivaciones directas del costo objetivo de la oferta. IDs, nombres comerciales
y enlaces no son predictores iniciales.

**Baseline:** mediana del costo de pares comparables, calculada con datos de
entrenamiento. **Primer modelo:** Elastic Net sobre condiciones del producto,
con codificación de categorías e imputación dentro del pipeline. Comparar
Gradient Boosting si hay mejoras fuera de muestra; no incorporar XGBoost por
defecto. Evaluar si conviene un modelo por familia en función de cobertura.

**Score:** residual `costo_observado - costo_esperado`; menor costo condicional
puede implicar mayor atractivo. Transformación a 0–100 con distribución de
residuales de validación fuera de muestra del período de entrenamiento, no
residuales in-sample del modelo final. Fijar calibración y conservar costo
esperado, residual y percentil como explicación. No es una recomendación personalizada.

**Evaluación:** separar por fechas de snapshots, nunca partir filas aleatoriamente
entre días. Reportar MAE/RMSE por familia, denominación y tasa; error por
entidad, estabilidad del ranking y proporción de ofertas elegibles. Añadir un
holdout de entidades para comprobar generalización a prestadores nuevos.
Conservar todas las observaciones en las tablas; agrupar o ponderar repeticiones
solo en el dataset de entrenamiento mediante una regla documentada. Las claves
provisionales no demuestran identidad comercial estable entre capturas.

**Limitación actual:** hay 13 capturas completas, repartidas entre el 7 y el 23
de septiembre, no 46.586 productos independientes. Se puede construir un
baseline y un experimento transversal, pero no demostrar estabilidad temporal
de un modelo productivo con ese corto histórico. Antes de aceptar entrenamiento,
reportar días independientes, repeticiones, cobertura del target, tamaños por
grupo y viabilidad de train/validación/test. Los umbrales se fijarán en ese
informe previo, no después de ver el resultado del modelo.

**Matriz prevista:** una fila por `observacion_id`, con split, condiciones y
objetivo seleccionado. **Score previsto:** `(observacion_id, version_modelo)`
con score, costo esperado, residual, grupo comparable y elegibilidad.

## IEF — Estrés Financiero Empresarial

**Unidad:** CUIT-mes. **Fuentes:** C/empresa_mes y deuda_entidad_mes; empresas,
consultas y acreedores para universo, disponibilidad y detalle; empresa_subsector
y subsectores para comparaciones sectoriales. A podrá agregar contexto temporal.

| Familia de features | Construcción inicial | Condición |
|---|---|---|
| Exposición | log1p de deuda en miles de pesos; cambios a 1/3 meses y ventanas a 3/6 meses. | Solo meses observados; cambios relativos con denominador positivo. |
| Acreedores | Cantidad activa, entradas/salidas, HHI y participación del principal. | Concentración solo con saldo positivo; entradas/salidas requieren revisar cambios de denominación, pues el ID de C es técnico y no un identificador jurídico estable. |
| Situación | Situación activa, proporciones por situación y cambios mensuales. | Situaciones desconocidas y falta de saldo no se convierten a categoría 1. |
| Señales legales | Revisión y proceso judicial, y cambios de esas señales. | Respetar flags conocidos/desconocidos de las entidades reportadas. |
| Trayectoria/pares | Desvíos respecto de historia propia y referencias sectoriales. | Ventanas pasadas; referencias ajustadas en entrenamiento; 100 empresas únicas. |
| Contexto A, posterior | Tasas/condiciones agregadas disponibles al cutoff. | No forzar la incorporación si faltan vintages o equivalencia temporal. |

Lags sobre una grilla mensual por CUIT. No eliminar huecos antes de desplazar
filas. Una ventana de 3 meses exige 3 observaciones válidas; una de 6 exige 6.
La primera deuda positiva luego de un cero observado es un evento, no una
variación porcentual infinita. Un mes ausente permanece nulo. En pertenencias
múltiples, una empresa sigue aportando una fila al entrenamiento; cualquier
benchmark sectorial múltiple debe definir una combinación sin duplicar su peso.

**Baseline:** score explícito de indicadores observables/percentiles de referencia,
con reglas publicadas. **Primer modelo:** Isolation Forest como detección de
anomalías multivariadas. Comparar con baseline y, si aporta valor, LOF/One-Class
SVM o agrupación de pares. Un score de anomalía no equivale automáticamente a
estrés: revisar sus componentes y distinguir anomalías de mayor riesgo de
deuda baja, desendeudamiento u otros cambios benignos. Si no hay coherencia con
el constructo de estrés, no renombrar el resultado como índice de estrés validado.

**Calibración:** orientar el score de anomalía y fijar percentiles de referencia
en entrenamiento; guardar versión y mapping 0–100. El resultado no es
probabilidad de default ni calificación oficial.

**Evaluación:** cortes por meses, manteniendo todas las filas de un mes juntas,
más un holdout de empresas/grupos económicos para medir generalización cuando
sea factible. Ajustar preprocesamiento solo en train. Medir estabilidad entre
ventanas y semillas, sensibilidad, cobertura y revisión de casos extremos;
contrastar descriptivamente contra deterioro posterior donde sea observable,
sin usarlo para construir features. Con 100 empresas y 24 meses, las filas
no son observaciones independientes ni una muestra representativa nacional.

**Extensión supervisada, no inicial:** target `empeora en t+1` solo para dos meses
consecutivos, observados y con situación activa conocida. Excluir casos sin
observación y no imputar su etiqueta. Separar el target de los predictores;
embargo temporal para el horizonte y test final intacto. Los 37 empeoramientos
descriptivos actuales no justifican por sí solos entrenar un clasificador.

**Matriz prevista:** una fila `(cuit_normalizado, fecha)` con features,
disponibilidad y elegibilidad. **Score previsto:** `(cuit_normalizado, fecha,
version_modelo)` con score y factores descriptivos de la señal; revisar la
estrategia de explicación del modelo antes de afirmar contribuciones causales.

## Protocolo común de joins y validación

- Leer IDs como texto y verificar PK/FK antes de preparar features.
- Join de dimensiones many-to-one, excepto la pertenencia sectorial explícita.
  Comprobar filas y sumas antes/después; no entrenar sobre un panel multiplicado por subsectores.
- Unir contexto por disponibilidad y fecha de referencia mediante regla as-of;
  `fecha del dato <= cutoff` es necesaria pero no prueba fecha de publicación.
- Guardar lista de series, features, unidades, fórmulas, universo, cobertura,
  fuente, cutoff y split junto a cada dataset. Ajustar scalers, imputadores,
  codificadores, PCA, selección y calibración exclusivamente dentro de train.
- Para paneles, hacer splits por fechas únicas, no aplicar TimeSeriesSplit a
  filas individuales con muchas empresas u ofertas en el mismo período.
- Proteger un test final. Elegir hiperparámetros con folds internos; no cambiar
  definición de features o score a partir del resultado del test.
- Semillas fijas y comparación con baseline. Reportar métricas por grupo,
  dispersión entre ventanas y porcentaje excluido, no solo un promedio global.
- Conservar el carácter retrospectivo de A/C hasta disponer de vintages. B sí
  permite cortes por su fecha de captura. Una captura reciente con datos de un
  mes antiguo no hace que esos datos fueran conocidos en ese mes antiguo.

## Criterios de avance

| Etapa | Evidencia necesaria antes de avanzar |
|---|---|
| Tablas → features | PK/FK/tipos válidos; universos conservados; reconciliación y unidades documentadas. |
| Features → baseline | Diccionario de fórmulas, cutoff y elegibilidad; tests de lags, huecos y joins sin multiplicación. |
| Baseline → modelo | Target/constructo definido; cobertura suficiente por grupo; protocolo de splits fijado. |
| Modelo → score | Comparación fuera de muestra; estabilidad y calibración reproducibles; limitaciones visibles. |
| Score → web | Consumo del artefacto versionado, explicación y tratamiento de casos no elegibles. |

## Orden práctico

La matriz y el baseline **ICC** ya están preparados con A para el agregado
hipotecario ML PH. Antes de PCA/modelos, revisar causa de extremos, arrastres de
la fuente, poblaciones distintas, saturación y evaluación expansiva, conservando
un test realmente no inspeccionado. No presentar estas referencias como índice
nacional ni recalibrar sobre el bloque retrospectivo ya expuesto. En paralelo, seguir acumulando snapshots B. Después preparar **IEF** sobre el
panel ya disponible, empezando por baseline y anomalías. En IAP, empezar por el
baseline de pares y la auditoría de repeticiones/cobertura; avanzar a regresión
cuando su protocolo de evaluación sea viable. Ninguna fuente adicional se
incorpora sin una feature y un consumidor definidos.

## Fuentes técnicas

- Propuesta de Proyecto Final, secciones 9.1–9.3, incluida como `docs/propuesta.md`.
- Scikit-learn: [prevención de leakage y preprocesamiento](https://scikit-learn.org/stable/common_pitfalls.html).
- Scikit-learn: [validación temporal](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data).
- Scikit-learn: [PCA](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html).
- Scikit-learn: [Elastic Net](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNet.html).
- Scikit-learn: [Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).
