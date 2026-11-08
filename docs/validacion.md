# Validación del proyecto depurado

Verificación realizada el 21 de octubre de 2026, Buenos Aires.
La limpieza retiró archivos sustituidos y duplicados, compartió código e
insumos empresariales y conservó las decisiones metodológicas vigentes.

## Pruebas de código y datos

Se aprobaron 207 pruebas, sin omisiones en estas suites:

| Conjunto | Pruebas aprobadas |
| --- | --- |
| Features, evaluador, S1, FA1, PCA2, inflación, semántica y contrato ABC | 181 |
| Hipotecarios empresariales 0.1 | 8 |
| Cierre empresarial 0.2 | 8 |
| Otras series ICC | 10 |

Las suites del baseline anterior y de features 2.0 se retiraron por estar
sustituidas. Las pruebas vigentes cubren el método actual y no dependen de esos
artefactos nominales históricos.

## Matriz IEF 0.1 — verificación anterior

Se agregaron 20 pruebas para la matriz C a precios constantes. En esta etapa se
aprobaron 60 pruebas: las 20 nuevas y 40 existentes de inflación, semántica y
contrato relacional. Las 207 de la depuración corresponden a la verificación
anterior; el proyecto conserva ahora 227 pruebas distintas comprobadas entre
ambas etapas. No se reentrenaron los modelos ICC.

```bash
python -m unittest docs.validar_ief docs.validar_inflacion docs.validar_semantica docs.validar_relacional -q
python ml/ief.py
```

La matriz conserva 2.400 filas y 100 empresas, sin agregar huecos en esta
consolidación. Hay 2.047 filas elegibles: train 875, validación 587 y evaluación
585. El bundle contiene matriz y protocolo; no hay modelo IEF entrenado.
La reproducción en un destino independiente produce los mismos dos archivos.
Los hashes de las 342 fuentes y de todas las tablas consolidadas se verificaron
nuevamente sin diferencias. Las fórmulas, los casos límite y los motivos están
en `features_ief.md`; el experimento previsto está en `plan_ief.md`.

## Tratamiento IEF 0.2 — vigente

El tratamiento agrega 11 pruebas a las 20 de la matriz: 31 pruebas IEF, más
40 regresiones existentes, suman 71 pruebas aprobadas en esta etapa. El proyecto
reúne 238 pruebas distintas verificadas entre la depuración y las etapas IEF;
no se afirma una nueva ejecución de todas las suites ICC ni de los notebooks.

La razón logarítmica real reemplaza al crecimiento porcentual como predictor del
primer bosque, conservando el porcentaje original en la matriz. No se imputan,
recortan, redondean ni eliminan extremos; los otros cinco predictores mantienen
su definición. La cobertura continúa en 2.047 de 2.400 filas. El detalle por
acreedor reconcilia con los agregados y los seis extremos seleccionados de train
coinciden con las capturas originales, con hashes verificados.

Las referencias de diagnóstico usan solo las 875 filas elegibles de train y se
persisten para aplicación sin refit. Se prueban la invariancia de esas referencias
ante cambios posteriores, conservación de filas y originales, ceros, simetría del
logaritmo, estabilidad numérica y detección de incompatibilidad de referencias.
La bandera de rango train es contexto; ninguna bandera o ID adicional entra al
modelo. Las fuentes y tablas consolidadas siguen intactas. Se verificó la
reproducción idéntica de ambos archivos, también desde el ZIP extraído.

En la etapa de tratamiento no se entrenó Isolation Forest. Se documenta la sensibilidad futura con el
crecimiento porcentual original frente al logarítmico, sin elegir a partir de
resultados de la evaluación final.

## Baseline IEF 0.1 — vigente

Se agregaron 11 pruebas del baseline: las 42 pruebas IEF y las 40 regresiones de
inflación, semántica y contrato suman 82 aprobadas en esta etapa. El proyecto
reúne 249 pruebas distintas verificadas entre las etapas anteriores y esta;
no se afirma una nueva ejecución de las suites ICC autónomas o de los notebooks.

```bash
python ml/baseline_ief.py
python -m unittest docs.validar_ief docs.validar_inflacion docs.validar_semantica docs.validar_relacional -q
```

El baseline conserva todas las columnas y filas de la matriz tratada 0.2 y
agrega criterios de prioridad mensual, posiciones con intervalos de empate y
participaciones top 5/top 10. Hay 2.047 filas con prioridad y 353 sin ranking,
con sus motivos preservados. Los tres primeros meses quedan sin prioridades.
En los 21 meses con elegibles, las participaciones suman 5 y 10, respectivamente;
el top 5 cruza un empate en 7 meses y el top 10, en 20.

Se verifican jerarquía lexicográfica, componente positivo del aumento,
invariancia ante orden de entrada o CUIT de los empatados, independencia de
meses posteriores, conservación de columnas, filas y exclusiones, detección de
matrices alteradas y publicación atómica e inmutable. La aplicación no ajusta
referencias de tratamiento ni parámetros del baseline. Las 342 fuentes y las
13 tablas consolidadas conservan sus hashes. El código y los dos archivos del
tratamiento 0.2 permanecen intactos.

El ZIP extraído reproduce los dos archivos del baseline byte a byte y aprueba
las 42 pruebas IEF. En esa etapa el bosque estaba pendiente; la regla y sus
limitaciones se documentan en `baseline_ief.md`. La etapa siguiente lo incorpora.

## Bosque IEF 0.1 — entrenamiento y comparación

Se aprobaron 96 pruebas: 14 nuevas del modelo, 42 previas de IEF y 40 de inflación,
semántica y contrato relacional. El proyecto acumula 263 pruebas distintas
verificadas entre etapas; no se afirma una nueva ejecución de todas las suites
ICC autónomas ni de los notebooks anteriores.

```bash
python -m unittest docs.validar_modelo_ief docs.validar_ief docs.validar_inflacion docs.validar_semantica docs.validar_relacional -q
```

Se verificó que modificar predictores posteriores al corte no cambia los bytes
del estimador ni su referencia; las fechas impiden convertir validación en train.
El artefacto usa 875 filas, 98 empresas, seis predictores, 300 árboles y semilla
42. Se conservan las 2.400 filas y sus columnas: 2.047 tienen score y 353 quedan
con score, posición y pesos nulos. La calibración empírica congela los empates
sobre train y el ranking usa score crudo, incluso cuando el percentil se satura.

El scoring desde el modelo guardado coincide byte a byte con el CSV del
entrenamiento; las pruebas bloquean cualquier fit al aplicarlo. Se verifican
hashes y versiones antes de deserializar. Otra corrida completa reproduce los
cuatro archivos del bundle, incluido joblib, con bytes idénticos. Se verificó
la misma reproducción desde el ZIP extraído y sus 56 pruebas IEF.

Las semillas 43/44 y la variante de crecimiento original son diagnósticos
predefinidos, entrenados solo en train; sus modelos no se distribuyen. La
comparación con baseline usa las mismas filas, medias mensuales y top-k
fraccional. La composición del top 5 y las correlaciones entre predictores se
reportan descriptivamente. No se construyó un target ni se afirma anticipación.

Las 342 fuentes, las 13 tablas, el código de preparación y baseline, y sus
bundles previos conservan sus bytes. El contraste t+1, holdout por grupos,
fichas, revisión humana y notebook continúan pendientes. Resultados en
`modelo_ief.md` y en el informe del bundle `bosque_v0.1`.

## Notebooks

Se ejecutaron las celdas de los cuatro notebooks con IPython, en procesos
locales independientes y con las consultas de red bloqueadas: A, 23 celdas;
B, 32; C, 20; análisis conjunto, 19. Todas terminaron correctamente.
Esta verificación ejecuta código y visualizaciones; no utiliza el transporte
de un servidor Jupyter. Los resultados guardados originales se conservan.
El notebook A usa visualización Plotly integrada en VS Code/Jupyter en lugar
de exigir un navegador externo.

## Integridad y reproducción

Las 342 fuentes que declara la consolidación vigente siguen presentes y sus
hashes SHA256 coinciden. También se comprobaron los archivos de salida que
declara su metadata. Se conservan los snapshots B y las capturas C requeridos
por los notebooks y por la procedencia del dataset.

La evaluación empresarial 0.1 se ejecutó con los módulos ML centrales y las
fuentes compartidas. Sus columnas numéricas coinciden con la entrega anterior
con tolerancia 1e-10. La comparación de pesos y el cierre 0.2 se recalcularon
con las rutas compartidas.

Los siete índices vigentes coinciden con los anteriores, con diferencia máxima
cero en sus puntajes. La limpieza no modifica fórmulas, pesos, cortes,
referencias, aceptación de modelos ni restricciones de reserva.

## Evidencia de la depuración

`archivos_retirados.csv` registra ruta, tamaño, hash y motivo de cada retiro.
`verificacion_proyecto.json` contiene el resultado estructurado de las pruebas,
integridad y comparación de índices. `INFORME_DEPURACION.md`, en la raíz,
explica qué se conserva y qué se regenera bajo demanda.

## Alcance

Entorno verificado: Python 3.12.14, pandas 2.2.3, numpy 2.3.5, scikit-learn 1.8.0,
scipy 1.17.0, matplotlib 3.10.8, xlrd 2.0.1 y openpyxl 3.1.5.
Las dependencias están reunidas en `requirements_icc.txt`.
La verificación no habilita el global, predicción, causalidad, acceso individual,
alertas operativas ni integración web. La ejecución en Windows debe usar un
entorno compatible; no se afirma una ejecución en el equipo del autor.
