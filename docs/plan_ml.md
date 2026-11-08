# Plan de análisis y modelado

Estado metodológico consolidado al 15 de octubre de 2026. Proyecto depurado el
21 de octubre. Protocolo temporal del piloto 3.1; features 3.0; S1 4.0;
FA1 4.1 y diagnóstico PCA2 4.2. La guía de ejecución es `../LEEME_ICC.md`.

## Estado vigente

Hay siete ICC particulares experimentales para uso descriptivo interno, nueve
indicadores parciales de volumen y dinámica, siete series de contexto y una
diferida. El índice global no está definido. La matriz IEF 0.2 está implementada
con deuda real, seis predictores y 2.047 filas elegibles. El baseline mensual
y el bosque están implementados; quedan pendientes las evaluaciones secundarias
IEF, IAP, la web y las alertas operativas.

| Segmento | Serie | Peso costo | Peso momentum |
| --- | --- | --- | --- |
| Hipotecarios PH ML | 927 | 80% | 20% |
| Hipotecarios PyMEs ML | 935 | 60% | 40% |
| Hipotecarios No PyMEs ML | 936 | 80% | 20% |
| Prendarios PH ML | 960 | 50% | 50% |
| Prendarios PyMEs ME | 979 | 50% | 50% |
| Personales sector privado ML | finserprom_personales_ml_privado | 60% | 40% |
| Tarjetas sector privado ME | finserprom_tarjetas_me_privado | 60% | 40% |

Cada índice usa referencias propias. Sus niveles no se ordenan ni se promedian
como si expresaran condiciones absolutas comparables. ML usa saldo real en ARS;
ME usa USD equivalentes nominales y no se deflacta con IPC argentino.

## Función interna del ICC

El ICC ayuda a localizar cambios y revisar su origen por segmento, dimensión y
serie. Su puntaje se consume internamente. La información destinada al usuario
explica qué cambió, qué componentes contribuyeron y cuáles son las fuentes,
fechas, cobertura y limitaciones. Los aportes algebraicos no prueban causalidad.

Se deben distinguir nivel y dirección: un contexto débil que mejora y otro
favorable que empeora pueden producir valores parecidos o invertir su orden.
El saldo vigente no mide acceso individual, ofertas disponibles ni originaciones.
Las tasas utilizadas son proxies parciales y no equivalen al costo financiero
total de cada población de saldos.

## Piloto hipotecario PH

Secuencia desde la raíz del proyecto:

1. `actualizar_bases.py` integra fuentes y genera las 13 tablas bajo contrato 2.0.
2. `ml/features.py` prepara 14 candidatas con cobertura y procedencia.
3. `ml/baseline.py` ajusta las referencias S1 exclusivamente en train.
4. `ml/train.py` evalúa explícitamente `pca`, `factor_analysis` o `pca2`.
5. `ml/score.py` aplica el artefacto elegido sin refit.

La consolidación distribuida es `20261006_231124_214604`. El core contiene
saldo real R, crecimiento real trimestral g y TNA UVA r. Se conserva la
población de saldos PH y la diferencia con la población de la proxy de tasa.
No se imputan faltantes.

S1: `B = 100 V (0.80 C + 0.20 M)`, con `V = R/(R+R0)`,
`C = logística((r0-r)/sr)` y `M = logística(g/sg)`.
Las medianas, escalas y pisos se fijan en los mismos 60 meses comunes de train.
El punto R0/r0/g=0 vale 25 y no se interpreta 50 como neutralidad económica.
Los criterios completos están en `criterios_datos.md`, secciones 9 a 11.

| Bloque | Calendario | Meses core | Función |
| --- | --- | --- | --- |
| Train | Agosto 2016 a febrero 2022 | 60, desde marzo 2017 | Único ajuste de referencias y modelos. |
| Validación | Marzo 2022 a diciembre 2023 | 22 | Contraste con criterios fijados. |
| Retrospectiva | Enero 2024 a junio 2026 | 30 | Aplicación descriptiva posterior a la decisión. |
| Reserva | Desde julio 2026 | Sin score | Requiere protocolo separado. |

No hay shuffle ni test intacto nuevo. Los controles conservan sus mínimos:
60 meses train y 18 de validación. La validación ya fue examinada; se explicita
el carácter exploratorio de los contrastes sucesivos.

### Decisiones sobre los candidatos

PCA1 mejora 14,21% el MSE medio de validación, pero deteriora la reconstrucción
de volumen y momentum más allá del máximo por columna: queda rechazado.
FA1 también incumple los controles y no sustituye S1.
PCA2 explica 90,25% de la varianza de train y recupera volumen; su MSE de
validación es 19,62% mayor que el comparador V/H de dos dimensiones. No tiene
una agregación escalar aprobada. El índice vigente continúa siendo S1.
Se conservan los JSON, informes y scores canónicos bajo
`data_analytics/modelos_icc/20261006_231124_214604/`.

## Extensiones empresariales

La evaluación de hipotecarios empresariales usa código ML compartido del piloto
con un adaptador explícito de población y de tasa nominal fija/repactable.
`experimentos/icc/hipotecarios_empresariales_v01/` conserva el experimento y sus
rechazos PCA1/FA1/PCA2. Los candidatos 80/20 son una referencia histórica para
comparar pesos y no sustituyen el cierre 0.2.

La comparación está en `experimentos/icc/pesos_empresariales_v01/`.
El cierre vigente, en `experimentos/icc/hipotecarios_empresariales_v02/`, aplica
60/40 a PyMEs 935 y conserva 80/20 en No PyMEs 936. Se mantienen las referencias
de train y se contrastan 37 trimestres ECC observados. La ECC empresarial no
coincide exactamente con la línea hipotecaria: se conserva esta limitación.
No se afirma optimalidad estadística ni validación operativa de los pesos.

## Cierre de las otras series

Se evaluaron 21 series adicionales y se conservaron los tres ICC hipotecarios
previos. El cierre de `experimentos/icc/series_v01/` publica cuatro ICC nuevos,
nueve parciales IVD, siete series de contexto y una diferida. El registro de
estados está en `resultados/registro_decisiones.csv` dentro de esa carpeta.

Los cuatro índices nuevos pasan el protocolo numérico de esta versión. Las
correlaciones externas débiles o negativas, la sensibilidad temporal y las
proxies imperfectas permanecen explícitas. Superar esos controles no valida
por sí solo una medida integral de condiciones crediticias.
Los 28 controles por serie/peso están tabulados en `controles_escenarios.csv`.
Las trayectorias de todos los candidatos son regenerables desde los snapshots;
se distribuyen las salidas seleccionadas, parciales y métricas completas.
El informe de cierre contiene las decisiones y sus fundamentos.

## Trabajo pendiente del ICC

1. Formalizar un constructo común antes de combinar índices particulares.
2. Resolver comparabilidad de escalas propias, ML/ME, saldos medios/cierres,
   solapamiento de totales y subproductos, cobertura comercial y residuales.
3. Predefinir pesos globales, calendario, cobertura mínima y ausencias. No
   rellenar faltantes con cero ni renormalizar pesos silenciosamente.
4. Implementar y evaluar la observabilidad: recorrido global, segmentos,
   componentes y series con explicaciones que reconcilien con las fórmulas.
5. Validar la utilidad de las señales frente a observar directamente las
   variables. Distinguir cambios económicos de revisiones o cambios de cobertura.
6. Definir un protocolo prospectivo independiente antes de habilitar operación;
   el piloto exige al menos 12 nuevos meses completos para esa etapa.

El ICC global agrega condiciones de segmentos compatibles; no es un promedio
de ICC, IAP e IEF. El acta de bloqueo está en
`experimentos/icc/series_v01/resultados/decision_global.json`.

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

**Avance del 21 de octubre:** matriz y tratamiento 0.2 implementados en `ml/ief.py`.
Protocolo específico: `plan_ief.md`; diccionario, elegibilidad y cobertura:
`features_ief.md`. Las familias siguientes describen posibles extensiones;
el primer core queda restringido a las seis variables de ese diccionario.
El baseline de prioridad mensual está implementado en `ml/baseline_ief.py`,
con reglas, empates y resultados en `baseline_ief.md`. El bosque IEF 0.1 está entrenado con 875 filas, con puntuación y comparación
retrospectiva frente al baseline. Ver `modelo_ief.md`. El contraste t+1,
los grupos y la revisión humana de casos continúan pendientes.

**Unidad:** CUIT-mes. **Fuentes:** C/empresa_mes y deuda_entidad_mes; empresas,
consultas y acreedores para universo, disponibilidad y detalle; empresa_subsector
y subsectores para comparaciones sectoriales. A podrá agregar contexto temporal.

| Familia de features | Construcción inicial | Condición |
|---|---|---|
| Exposición | log1p de deuda en miles de pesos de diciembre de 2016; cambios reales a 1/3 meses y ventanas a 3/6 meses. | Solo meses observados; cambios relativos con denominador positivo. |
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

**Matriz implementada:** una fila `(cuit_normalizado, fecha)` con seis features,
contexto, split, disponibilidad, elegibilidad y motivos de ausencia. **Score previsto:** `(cuit_normalizado, fecha,
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
| Score → web / observabilidad | Consumo del artefacto versionado, explicación y tratamiento de casos no elegibles; ICC se consume internamente con trazabilidad y doble clic, sin mostrar su puntaje al usuario final. |
| ICC particulares → global | Constructo común, escalas y pesos justificados, control de solapamientos, cobertura y descomposición reconciliada; fórmula global aprobada antes de evaluar resultados. |
| ICC → señales operativas | Valor añadido frente a variables directas, reglas predefinidas, calidad/disponibilidad verificadas y evaluación prospectiva separada. |

## Orden práctico

1. Reproducir el piloto hipotecario, revisar sus componentes, episodios y flags,
   y definir qué información consumirá internamente la observabilidad.
2. Evaluar las demás series y aprobar el alcance, dimensiones y elegibilidad de
   cada índice particular. Construir y validar los particulares por etapas.
3. Formalizar el ICC global con agregación, pesos, cobertura y descomposición
   explícitos; no extender el nombre nacional a partir del piloto hipotecario.
4. Implementar el recorrido global → particulares → dimensiones → series y
   contrastar la utilidad descriptiva frente a observar variables por separado.
5. Conservar los rechazos PCA/FA y el diagnóstico PCA2 como evidencia. Cualquier
   reformulación requiere nueva versión, criterios previos y evidencia adicional.
6. Acumular datos prospectivos y trazabilidad de revisiones antes de habilitar
   señales operativas. Seguir preparando B para IAP y C ajustada para IEF cuando
   se aborden esos índices.

Ninguna fuente adicional se incorpora sin una feature y consumidor definidos.

## Fuentes técnicas

- Propuesta de Proyecto Final, secciones 9.1–9.3, incluida como `docs/propuesta.md`.
- Scikit-learn: [prevención de leakage y preprocesamiento](https://scikit-learn.org/stable/common_pitfalls.html).
- Scikit-learn: [validación temporal](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data).
- Scikit-learn: [PCA](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html).
- Scikit-learn: [Elastic Net](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNet.html).
- Scikit-learn: [Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).
