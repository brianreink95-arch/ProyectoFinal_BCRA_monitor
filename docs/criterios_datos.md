# Criterios de datos y plan de ajuste por inflación

Versión 4.2 — 6 de octubre de 2026 (Buenos Aires). Features 3.0; contrato relacional 2.0.

Ubicación en el proyecto: `docs/criterios_datos.md`.
Estado: preparación económica A/C y 14 candidatas ICC implementadas; PCA1/FA1 evaluados y rechazados; PCA2 implementado como diagnóstico bidimensional sin agregado escalar. Índice vigente baseline S1. Protocolo temporal 3.1 sin cambios.

## 1. Propósito y alcance

Preparar magnitudes monetarias comparables en el tiempo antes de continuar el feature engineering. Conservar datos originales y valores nominales, incorporar un deflactor oficial y producir valores a precios constantes únicamente donde las unidades y el significado lo permitan.

El primer consumidor es el ICC hipotecario. El mismo deflactor servirá para los saldos de Base C destinados al IEF. Los montos de Base B se incorporarán cuando su comparación temporal sea necesaria para el IAP y su denominación esté validada. No se generan señales, tablas ni variantes adicionales sin consumidor.

La corrección inflacionaria no identifica nuevos desembolsos, no resuelve reclasificaciones ni certifica la contemporaneidad de los saldos. “Real” significa expresado a precios constantes bajo el criterio indicado.

## 2. Dónde se documentan los criterios

| Documento | Responsabilidad |
|---|---|
| `docs/criterios_datos.md` — este documento | Criterios económicos de preparación: inflación, unidades, moneda, tiempo, comparabilidad y pendientes. |
| `docs/diseno_tablas.md` y `config/esquema_tablas.json` | Tablas, columnas, unidades, claves, tipos, relaciones y validación del contrato. |
| `docs/features_icc.md` | Registro de candidatas ICC, fórmulas, ventanas y elegibilidad por consumidor; selección definitiva pendiente. |
| `docs/plan_ml.md` | Baselines, modelos, evaluación y secuencia de trabajo. |
| `protocolo_icc.json` de cada corrida | Referencias efectivamente ajustadas, splits, pesos y trazabilidad de un experimento. No reemplaza la documentación ni se edita para fabricar resultados. |

Actualizar los documentos afectados y enlazar este archivo desde ellos. Evitar copiar el criterio inflacionario completo en cada documento. Los notebooks explican resultados; no son la única ubicación de una regla operativa.

## 3. Decisiones aceptadas

| ID | Criterio | Estado |
|---|---|---|
| D01 | Usar IPC nacional, nivel general, publicado por INDEC, con base diciembre de 2016 = 100. | Implementado: niveles oficiales INDEC; 117 meses, diciembre 2016–agosto 2026. |
| D02 | Inicio del análisis a precios constantes: diciembre de 2016. Mantener la historia nominal anterior. Cada serie conserva su propia cobertura. | Aceptado. |
| D03 | Expresar valores constantes en pesos de diciembre de 2016, conservando la escala validada de la columna: pesos, miles u otra unidad explícita. | Implementado en seis stocks ICC: millones de ARS contrastados; C conserva miles de ARS. Resto de stocks A excluido del ajuste. |
| D04 | Fórmula: `valor_constante = valor_nominal * 100 / ipc_nacional`. El índice debe ser positivo, del mismo mes y de la misma versión de fuente. | Aceptado. |
| D05 | No reconstruir el deflactor principal encadenando la serie BCRA 27. Esa serie contiene variaciones y cambios de cobertura; conservarla como contexto histórico. | Aceptado. |
| D06 | No recuperar automáticamente el antiguo ajuste CER. CER es un índice de actualización con rezago respecto del IPC; no es el deflactor principal elegido. | Aceptado. |
| D07 | No dividir tasas, porcentajes, cantidades, situaciones crediticias ni indicadores legales por IPC. Distinguir tasas nominales y tasas sobre UVA. | Aceptado. |
| D08 | No tratar la denominación del crédito como prueba de la unidad del importe publicado. Confirmar cómo está expresado cada campo antes de convertirlo. | Aceptado. |
| D09 | No imputar IPC ni saldos faltantes con cero, interpolación o arrastre. Un ajuste no calculable conserva el nominal y el motivo de ausencia. | Aceptado. |
| D10 | Ajuste principal mensual retrospectivo. Fecha de referencia no equivale a fecha de publicación ni de adquisición. | Aceptado; disponibilidad histórica verificable pendiente. |
| D11 | Preservar saldos cero observados y distinguirlos de meses ausentes. No borrar extremos ni winsorizar automáticamente después del ajuste. | Aceptado. |
| D12 | Mantener los CSV y extracción + transformación dentro de cada script de base. Compartir únicamente la lectura validada del deflactor y la operación matemática. | Aceptado. |
| D13 | ICC actual usa Base A e IPC. Base B no se mapea a ICC: snapshots sin solapamiento histórico elegible; queda para IAP. | Implementado en el alcance de features y plan. |
| D14 | Stock es saldo vigente, no oferta, nuevos desembolsos, deudores ni acceso individual. No inventar indicadores de acceso sin fuente. | Aceptado; limitación explícita. |
| D15 | El índice debe considerar volumen y costo: tasa baja con volumen muy bajo no basta; con stock real igual, bajar tasa mejora costo. | Criterio aceptado; combinación/calibración pendiente. |
| D16 | Generar nivel, crecimiento anual, cambio absoluto y aceleración reales, y participaciones de los cinco destinos. | Implementado: 14 candidatas totales, todavía sin selección automática. |
| D17 | Elegibilidad depende de las variables del consumidor; no exigir las 14 para cualquier modelo. | Implementado con lista explícita y perfiles diagnósticos. |
| D18 | Cortes explícitos y mínimo de 60 meses; no shuffle ni recorte automático del mínimo. Toda modificación se registra. | Mínimo conservado; cortes revisados por D21. |
| D19 | Referencia normalizada de volumen, interacción con costo, pesos y umbrales requieren decisión justificada y ajuste solo en train. | Pendiente; no se inventan cocientes ni score. |
| D20 | Preservar artefactos anteriores y versionar cambios de significado/ruta. | Features 3.0 en subcarpeta propia; contrato continúa 2.0. |
| D21 | Extender train hasta febrero de 2022, incorporando enero/febrero; validación desde marzo de 2022 hasta diciembre de 2023. Retrospectiva/reserva sin cambios. | Aprobado explícitamente el 6/10/2026: diagnóstico 60 train, 22 validación, 30 retrospectiva. Comparación de seis: 57 train; todas las 14: 51. Calibración sigue pendiente por metodología. |
| D22 | Adoptar íntegramente el paquete S1 recomendado por el juez: core R/g3/r, fórmula de volumen × costo/momentum, PCA1 y todos sus controles predefinidos. | Autorización explícita del usuario el 6/10/2026: “Quiero empezar con la implementación según sugiere el juez”. Implementado como experimento 4.0; no autorización de uso operativo. |
| D23 | Evaluar análisis factorial de un factor sobre core R/g3/r; reutilizar baseline, muestra y criterios económicos, distinguiendo cargas de pesos posteriores. | Autorización del usuario 6/10/2026: “empecemos la implementación de este método”. Implementado como experimento 4.1; FA rechazado, sin cambiar S1 ni habilitar reserva. |
| D24 | Evaluar PCA2 conservando core, referencias y cortes; separar representación 2D de agregación económica a un ICC escalar. | Pedido del usuario 6/10/2026: “seguimos con PCA de 2 componentes?”. Diagnóstico4.2 implementado; no se definió ni aprobó un score PCA2. |

En las participaciones internas del mismo mes, aplicar el mismo factor a numerador y denominador conserva el resultado. En C ocurre lo mismo con HHI y participaciones por acreedor/situación calculadas dentro de una empresa-mes. No agregar versiones “reales” redundantes de esos ratios.

## 4. Estado inicial histórico — antes del ajuste por inflación

Este registro describe los cuatro scripts enviados antes de implementar inflación; no describe su estado actual. En aquella entrega no tenían ingesta de IPC nacional ni cálculo de montos a precios constantes.

| Archivo | Comportamiento inicial | Cambio implementado según el plan |
|---|---|---|
| `base_a.py` | Extrae BCRA, aplica la excepción analítica de 1199 y exporta series/observaciones. Adquisición con validación en staging. | Incorporar adquisición oficial de IPC, su validación y preparación de observaciones monetarias constantes. |
| `base_b.py` | Captura ofertas y exporta entidades/snapshots/ofertas con métricas nominales. | Mantener captura; preparar ajustes únicamente para campos monetarios y consumidores temporales justificados. No deflactar TEA/CFTEA, plazos ni ratios. |
| `base_c.py` | Consulta el maestro y exporta dimensiones y hechos; deuda en miles de ARS y panel empresa-mes nominal. | Ajustar saldos del detalle y del panel por el mes de referencia, preservando población y reconciliación. |
| `actualizar_bases.py` | Coordina mediante `lib/common.py`; no contiene reglas económicas. | Conservar esa responsabilidad. La dependencia del IPC y la trazabilidad requieren adaptar también el coordinador real en `lib/common.py`. |

También se deben adaptar `lib/relacional.py` cuando corresponda, `config/esquema_tablas.json`, el catálogo A y los consumidores afectados. Los cuatro scripts solos no contienen todo el contrato del proyecto.

## 5. Implementación entregada y plan de continuación

Los pasos 1–6 están implementados para el subconjunto habilitado. En el paso 7, las features reales 2.0 y la ampliación 3.0 están implementadas; el baseline real sigue bloqueado. El plan original se conserva abajo como seguimiento, con su estado actualizado.

### Resultado al 5 de octubre de 2026

- `base_a.py`: ingesta IPC oficial en `data_a/ipc/versions/<sha256>/`, publicación original y metadatos conservados, tabla normalizada y puntero atómico. `--ipc-only` actualiza solamente IPC; `--audit-units-only` contrasta el histórico ICC guardado; la extracción A normal realiza ambas tareas en staging.
- Inconsistencia de escala resuelta para 927 y 1145–1149: la API declara miles de ARS, pero los valores recibidos coinciden con los XLS oficiales en miles divididos por 1000 y redondeados. Cada una de las 115 observaciones de diciembre 2016 a junio 2026 coincide dentro de 0,5. Son **millones de ARS**, sin multiplicar ni sobrescribir los originales. Los XLS y el contraste de 690 observaciones quedan versionados en `data_a/unidades_icc/`.
- El campo `unidad` conserva el metadato declarado de la API. `unidad_validada=millones_ARS` y `validacion_escala=contraste_oficial_por_mes` describen la escala verificada. La habilitación exige coincidencia con el valor/mes del certificado: meses nuevos o valores revisados sin contraste quedan `unidad_no_validada`. Una adquisición A vuelve a auditar automáticamente. La auditoría rechaza discrepancias que exceden el redondeo para revisión explícita; no inventa factores.
- `base_a/observaciones.csv` agrega `valor_constante_dic2016` en la unidad validada; se ajustan seis stocks con consumidor ICC y se preserva toda la historia nominal. No se habilitan los demás 46 stocks pendientes ni las tasas.
- `base_c.py`: `monto_miles_pesos_dic2016` en detalle y cinco campos `*_constante_dic2016` en panel, todos en miles de pesos de diciembre de 2016. Se ajustan 28.968 registros de detalle y 2.400 empresa-mes; se conservan 100 empresas, huecos/cero observado, ratios y flags. Se exige reconciliación por empresa-mes antes de exportar.
- `base_b.py`: no crea importes constantes sin unidad, fecha y consumidor definidos. La decisión queda explícita en `summary.b.ajuste_ipc`; las tres tablas y los nominales se conservan.
- Contrato 2.0: **13 tablas**, una nueva `base_a/deflactor_ipc.csv` compartida. Sus columnas son `fecha_mes`, `ipc_nacional`, `factor_deflacion`, `periodo_base`, `version_fuente`. Los hechos ajustados agregan `ipc_fecha_mes` nullable y `estado_ajuste_ipc`; las FK entre bases se validan antes de publicar el puntero. C individual publica esa tabla de dependencia y consume el cache de A sin extraerlo.
- `actualizar_bases.py --refresh-ipc` actualiza únicamente IPC antes de consolidar. Sin flags, la transformación es offline. La metadata registra versión de IPC, fuente, actualización y adquisición, hashes, cobertura, contrato efectivo y `lib/precios.py`. `preparacion_precios.estado` distingue cobertura completa del subconjunto habilitado y preparación parcial; `status=completed` solo indica ejecución válida, no ajuste de todos los nominales.
- IPC inválido/ausente impide publicar el puntero; meses posteriores a su cobertura quedan nulos con `ipc_no_publicado`, sin arrastrar el IPC previo. Meses anteriores a diciembre de 2016 quedan `anterior_base`; fuentes ausentes siguen `sin_observacion`. El calendario del índice se exige continuo: un hueco interno se rechaza en vez de interpolarse.
- Nueva dependencia `xlrd>=2.0.1` para leer los XLS oficiales de la auditoría. No se añade otra base de datos ni un script extra de extracción.

Ejecutar desde la raíz:

```bash
python -m pip install -r requirements.txt
python actualizar_bases.py
```

El paquete incluye el cache validado de IPC/unidades. Para actualizarlo sin recapturar todas las fuentes:

```bash
python base_a.py --ipc-only
python base_a.py --audit-units-only
python actualizar_bases.py
```

Validaciones y comandos: `docs/validacion_inflacion.md`. El paquete original de inflación no reemplazó `ml/` ni los documentos ML. Posteriormente se implementó la matriz real 2.0 y ahora las candidatas 3.0; el baseline nominal permanece como historia, sin reutilizar sus percentiles para magnitudes reales.


### Paso 1 — Auditar unidades de las series que vamos a usar

Prioridad: 927 y destinos 1145–1149 del ICC, más la unidad de los saldos C. En el catálogo A hay 52 stocks con escala absoluta pendiente; no es necesario ampliar ahora el ICC a todos ellos.

Contrastar metadatos y observaciones con documentos/tablas oficiales, registrar la evidencia y resolver la escala sin inventar factores. Validar también denominación, población, significado y posibles cambios temporales. Una reconciliación interna apoya consistencia, pero no certifica la escala absoluta.

Si una escala absoluta queda pendiente, no presentar el nivel resultante como un importe validado. Una variación real relativa solo puede habilitarse por separado si se documenta y valida que la escala multiplicativa se mantiene entre los períodos y que el concepto es comparable. No usar esa excepción para sumar niveles o comparar montos de A con C.

Salida: actualizar el catálogo/criterios con evidencia y elegibilidad por serie, sin crear un Excel paralelo.

### Paso 2 — Incorporar la fuente oficial de IPC en Base A

Agregar funciones diferenciadas en `base_a.py` para descargar, interpretar y validar el índice nacional nivel general. Confirmar la URL y estructura vigente en el sitio oficial al implementarlo; no fijar un endpoint o nombre de archivo supuesto.

Guardar una copia versionada de la publicación original y la tabla normalizada en `data_a`. Registrar fuente, fecha de adquisición, período de publicación si está disponible, hash, cobertura y base. Evitar sobrescribir publicaciones históricas sin conservar la versión consumida.

Validar una observación por mes, nivel positivo, diciembre de 2016 = 100, calendario y cobertura. Comparar algunos niveles y sus variaciones contra la publicación oficial. Usar los niveles con su precisión publicada, no acumular porcentajes redondeados de BCRA 27.

Mantener la adquisición en staging y validar el IPC junto con el resto de A antes de publicar. Adaptar el `acquire()` actual: su validación temporal no puede depender por accidente del cache del proyecto definitivo.

La transformación offline consume el IPC guardado y validado; no hace solicitudes de red. Incorporar una dependencia de lectura solamente si el formato oficial la exige.

### Paso 3 — Definir una representación mínima y compartida

Publicar un único `base_a/deflactor_ipc.csv` por consolidación como tabla consumida por A/C y luego B si corresponde. PK mensual `fecha_mes`, al cierre del mes. Campos mínimos: fecha, nivel de IPC, factor `100 / IPC`, período base y versión de fuente. La procedencia detallada puede mantenerse en metadata de corrida para no duplicarla por fila.

Actualizar y versionar el esquema. No hacer pasar el IPC por un ID numérico BCRA ficticio. La nueva tabla tiene consumidores definidos y no es un output exploratorio sin propósito.

Usar un pequeño `lib/precios.py` para lectura/validación compartida, alineación mensual y deflación. La adquisición sigue en `base_a.py`; el helper no consulta internet ni importa el pipeline de otra base.

Guardar valores nominales y constantes en los hechos existentes, con nombres que expliciten el período base y una referencia al mes del deflactor. Agregar estado/motivo donde el ajuste no sea calculable. No sobrescribir `valor_original`, `valor_analitico`, `monto_miles_pesos` ni otros campos nominales para cambiarles silenciosamente el significado.

La unidad del nuevo campo conserva la escala de origen validada: por ejemplo, en C, miles de pesos de diciembre de 2016. Los datos anteriores a diciembre de 2016 permanecen nominales y con ajuste fuera de cobertura.

### Paso 4 — Aplicar el ajuste por base

**A — ICC:** ajustar stocks seleccionados con unidad ARS validada por el mes de referencia. No forzar stocks extranjeros o mixtos sin confirmar su unidad publicada y regla de conversión. Para stocks mensuales de cierre, usar el IPC del mismo mes. Mantener tasas e inflación sin esa operación. Las otras series se habilitan por criterios explícitos, no porque el campo sea numérico.

**C — IEF:** ajustar detalle empresa-acreedor-mes y empresa-mes con el mismo factor. Los huecos siguen nulos, los saldos cero observados siguen cero y se preservan las 100 empresas. No modificar situaciones ni flags. Si todas las unidades están verificadas, la suma de saldos constantes positivos por empresa-mes debe reconciliar con el total constante del panel.

**B — IAP:** no es necesario volver a capturar ofertas para introducir el ajuste. Auditar unidades de montos mínimos/máximos, ingresos, cuotas y cargos antes de seleccionarlos: un cargo puede ser porcentaje o importe, y una denominación UVA/USD no es un importe ARS confirmado. Ajustar solamente campos que se utilicen en comparaciones temporales. No agregar salidas ajustadas para tasas/ratios ni producir una tabla B adicional por defecto.

Para B, documentar si un importe describe la oferta vigente al snapshot o una fecha de información anterior. No escoger silenciosamente una de esas fechas. Si el IPC del mes correspondiente todavía no fue publicado, el valor constante retrospectivo queda pendiente; no usar el mes anterior como sustituto equivalente. Para evaluación en tiempo real, una regla con último IPC disponible sería otra medición y debe especificarse por separado.

### Paso 5 — Adaptar coordinación, metadata y publicación

En `lib/common.py`, verificar antes de transformar A/C que existe una versión válida y suficiente del IPC. Procesar con una misma versión de fuente y reflejar su hash, cobertura, base y fecha de adquisición en la corrida. Incluir `lib/precios.py` y la versión efectiva del esquema en los hashes/versiones; el coordinador original fijaba `schema_version='1.0'`, y la implementación ya consume el contrato 2.0.

Las ejecuciones individuales de C deben poder leer el IPC guardado sin extraer A automáticamente. Si falta cobertura, conservar nominales y estados no calculables; no publicar como completa una salida que incumpla el contrato declarado del ajuste. Mantener errores estructurales del índice separados de faltantes mensuales esperados.

Conservar publicación atómica, verificaciones de integridad y punteros solo después de validar la corrida. Evitar que un fallo de IPC publique una consolidación presentada como ajustada con datos inconsistentes.

### Paso 6 — Validar la preparación económica

Verificaciones necesarias:

1. En diciembre de 2016, nominal y constante coinciden porque IPC = 100.
2. Casos manuales confirman `nominal * 100 / IPC`; conservar precisión sin redondear anticipadamente.
3. Una prueba de variación real confirma `(1 + crecimiento_nominal) / (IPC_t / IPC_anterior) - 1`. Las tasas se expresan en fracción al aplicar esta identidad.
4. Un IPC duplicado, no positivo o de otra base se rechaza. Un mes ausente deja el ajuste nulo, con motivo, y no desplaza calendarios.
5. Fechas, unidades y filas se conservan después de los joins. A: many-to-one por mes; C: mismo número de empresas/filas y reconciliación de detalle-panel.
6. Tasas, ratios, situaciones y flags no cambian por deflación. Participaciones internas y HHI mantienen sus valores dentro de la tolerancia numérica.
7. La misma fuente y código producen la misma salida; los nominales guardados siguen intactos. Separar una adquisición autorizada de una transformación offline.
8. Comparar la serie nominal y constante y revisar los extremos de 2024. Persistir una explicación o la limitación; no asumir que todos desaparecen con inflación.

Registrar resultados en `docs/validacion.md`. No añadir un nuevo conjunto de outputs de control si alcanza con tests y metadata.

### Paso 7 — Features implementadas; baseline pendiente

Implementado en 2.0: crecimiento 1/3 meses y volatilidad sobre saldos constantes. La versión 3.0 incorpora nivel, crecimiento 12 meses, cambio absoluto trimestral, aceleración trimestral y los otros cuatro destinos. Se preservan nominales como fuente e historia; las matrices se distinguen por versión. No se multiplican variantes nominales/reales como predictores por defecto.

Primeras fechas teóricas si el saldo es completo desde diciembre de 2016: crecimiento mensual enero de 2017, trimestral marzo de 2017 y volatilidad de seis cambios junio de 2017. La elegibilidad efectiva debe recalcularse con cobertura y calidad, no darse por garantizada.

El baseline nominal anterior permanece como experimento histórico. Generar un nuevo protocolo y referencias a partir de features reales; no aplicar sus percentiles nominales a variables de significado distinto. Mantener cortes temporales explícitos y recalcular conteos: el train anterior tenía 65 meses y el mínimo era 60; si se mantiene el fin de train en diciembre de 2021 y la primera fila elegible pasa a junio de 2017, quedarían 55 meses, por debajo del mínimo de 60. Revisar esa viabilidad antes de ejecutar, documentando cualquier cambio sin optimizarlo con el bloque retrospectivo conocido.

Versionar cada artefacto cuyo significado cambia; el contrato sigue 2.0 porque no cambian tablas. El diagnóstico de cuatro predictores tenía 58 meses train hasta diciembre de 2021; D21 lo amplía explícitamente hasta febrero de 2022 y alcanza 60. Cumplir ese mínimo no convierte la especificación histórica en el índice aprobado; otras selecciones requieren su propia muestra. No entrenar PCA ni otros modelos hasta revisar el nuevo baseline y su interpretación. `docs/features_icc.md` y `docs/plan_ml.md` deben reflejar el cambio económico, no solo un nombre de columna.

## 6. Pendientes que el ajuste no resuelve

- Stocks A potencialmente arrastrados por la fuente; falta de identificación mensual por entidad.
- Cambios de población/concepto, diferencias entre saldos PH y tasas de otorgamientos UVA al sector privado.
- Escala absoluta no certificada y posible clasificación o revisión de extremos.
- Disponibilidad histórica/vintages para simular decisiones pasadas: mientras falten, declarar evaluación retrospectiva.
- Representatividad temporal del entrenamiento, saturación de percentiles y test no inspeccionado.
- B: historia corta e identidad provisional de ofertas; C: muestra intencional y nombres técnicos de acreedores.

Estos límites deben acotar interpretaciones. No son motivo para imputar, inventar etiquetas o demorar toda preparación cuando el subconjunto seleccionado sea validable.

## 7. Criterio de finalización de esta etapa

Se considera terminada cuando el IPC oficial está adquirido y versionado, las unidades del subconjunto elegido están validadas o tienen una exclusión explícita, las tablas nominales/constantes y su contrato son reproducibles, y la cobertura/exclusiones y pruebas están documentadas. Los criterios no deben depender únicamente de conversaciones o de notebooks archivados.

## 8. Fuentes y evidencia

- INDEC, IPC nacional y series históricas: https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31
- INDEC, Anuario estadístico 2016: tabla IPC nacional diciembre de 2016–julio de 2017, base diciembre de 2016 = 100: https://www.indec.gob.ar/ftp/cuadros/publicaciones/anuario_estadistico_2016.pdf
- BCRA, Informe de Política Monetaria julio de 2017: publicación del IPC nacional y datos retrospectivos enero–junio de 2017: https://www.bcra.gob.ar/publicaciones/informe-de-politica-monetaria-julio-de-2017/
- BCRA, metodología de tasas y coeficientes, actualización marzo de 2026: https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/tasmet.pdf
- Evidencia del proyecto: scripts compartidos el 5/10/2026; catálogo A y metodología guardada; diccionario de features y protocolo de baseline entregados el 4/10/2026.

El script histórico `04_build_credit_conditions_eda.py` calculaba stocks/CER. Esa evidencia explica una decisión anterior, pero no valida su reutilización con el catálogo actual.

### Evidencia adicional de unidades

- BCRA, por tipo de titular: https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/perser_priv.xls — hoja `Prest-Hip`, bloque ML, PH.
- BCRA, por destino: https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/perser_dest.xls — hoja `fis`, bloque ML: construcción, refacción, compra nueva/usada y otras.
- INDEC, CSV original: https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv ; metadatos: https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_metadatos.txt . Se selecciona `Codigo=0`, `Region=Nacional`, conservando precisión publicada.


## 9. ICC experimental vigente — S1, decisión D22

Se adoptó el paquete completo de S1 recomendado por el juez, incluidos los
parámetros que el triage había marcado para revisión. La autorización del usuario
cierra esa elección para este experimento, sin convertir criterios normativos en
evidencia económica. No se ensamblaron propuestas incompatibles de las sesiones.

**Core:** stock real hipotecario ML PH (R), crecimiento real trimestral (g) y
TNA UVA (r). La elegibilidad exige solo esas tres variables. Se conservan las
14 candidatas; participaciones y volatilidad son explicaciones opcionales.
Referencias sobre la misma muestra común de 60 meses de train, sin imputación,
shuffle, recorte de extremos ni ajuste con validación/retrospectiva/reserva.

Con logística L(x)=1/(1+exp(−x)), cuantiles lineales y parámetros de train:

- R₀=mediana(R), estrictamente positiva; r₀=mediana(r).
- sᵣ=max(IQR(r)/1,349; 0,10 pp); s𝗀=max(IQR(g)/1,349; 0,50 pp).
- V=R/(R+R₀); C=L((r₀−r)/sᵣ); M=L(g/s𝗀).
- **B=100 V (0,80 C + 0,20 M)**, sin segundo percentil.

Pesos, formas y pisos son normativos; medianas/IQR son aprendidos. R₀ es una
referencia interna de saldo, no suficiencia social. R≤0,25R₀ implica B≤20;
R=0 implica B=0 si g está disponible. Si falta g, el consumidor conserva nulo y
motivo. Igual R y g con menor r mejora costo. El punto R₀/r₀/g=0 vale **25**;
50 no es neutralidad, probabilidad ni umbral de favorabilidad.

**Candidato ML:** PCA1 full, sin whitening ni búsqueda. Entradas
[log1p(R/R₀), −r, asinh(g/s𝗀)], estandarizadas con media y std poblacional de
train. Std≤10⁻¹² rechaza PCA. Orientación global a costo positivo; todas las
cargas deben ser no negativas y sus fracciones L1 ≥[0,20;0,20;0,10]. No tomar
abs ni borrar cargas. f₀=mediana_train(f), s_f=max(IQR(f)/1,349;10⁻⁶),
**P=100 V L((f−f₀)/s_f)**. Una dirección inválida deja solo un factor diagnóstico.

### Contrato de evaluación predefinido

| Control | Regla de aceptación |
|---|---|
| Cobertura | ≥60 train, ≥18 validación; cortes D21 sin cambios. |
| Economía | Cero violaciones con tolerancia 10⁻⁹; volumen y momentum crecientes, menor tasa mejora, R≤0,25R₀ limita score≤20. |
| Sensibilidades B | Peso momentum 0/0,30; R₀ ×0,75/1,25; ambas escalas ×0,75/1,25. Además g1, delta_stock y cambio_tasa. Cada alternativa exige rho≥0,90 y MAE≤10 en train y validación. |
| Alternativas | Intersección con core; mínimo60. Escala IQR/1,349 con piso0,50pp para g1, 1 millón ARS dic2016 para delta_stock, 0,10pp para delta_tasa. C_alt=0,8C+0,2L(−delta_tasa/s_delta). Sin ganador ex post. |
| Perturbaciones PCA | Seis ajustes ±10% por columna de Z ya estandarizada, sin reestandarizar; coseno≥0,95 en coordenadas originales y rho_val≥0,90; cargas admisibles. |
| Reconstrucción | MSE val al menos10% menor que rectas por input ajustadas en train contra B; ninguna columna >25% peor. Error comparador≤10⁻¹²: inconcluso/rechazo. |
| Saturación | ≤10% de validación con mapa latente≤1 o≥99, antes del gate V. |

La grilla económica usa R/R₀={0;0,01;0,10;0,25;0,50;1;2;5},
r=max(0,{0;r₀−2sᵣ;r₀;r₀+2sᵣ}) y g={−2s𝗀;0;2s𝗀}. Son escenarios de
inputs independientes, no historias donde el crecimiento se recalcula al variar R.

P sustituye B solo si **todos** los controles pasan. Si falla sensibilidad de B,
el default sigue visible como `experimental_sensible`; tampoco habilita PCA ni
uso operativo. Si PCA falla, el índice usa B experimental, conserva el candidato
rechazado cuando sus cargas son admisibles y expone cada motivo. No se bajan
umbrales para obtener un modelo aceptado. No hay CV interna aprobada: exactamente
60 meses no permiten folds con train≥60 y validación dentro de train. Los dos
bloques de11 meses de validación son diagnósticos de aplicación, sin refit.

### Resultado sobre el último CSV del usuario

Corrida de origen `20261006_231124_214604`, SHA256
`4ad16b4e7e2847b3dda25fa5ec3c29560ef7f30158f7474c00ec37cef787b382`.
Train60 (marzo2017–febrero2022), validación22, retrospectiva30. S1 pasa economía,
las9 sensibilidades, cargas, las6 perturbaciones y saturación (0/22).
PCA reduce MSE medio val14,21%, pero MSE de volumen es2,224 veces el comparador
y de momentum10,894 veces. Límite por columna:1,25. **PCA rechazado por reconstrucción**.
Se generan112 meses del índice con B, manteniendo321 filas y reserva sin score.

La entrada independiente se validó por7 identidades internas y metadatos, pero
no adjunta las fuentes de esa corrida: `fuentes_reconstruidas=False`. La prueba
contra consolidación local sí reconstruye sus fuentes y reproduce el resultado;
no sustituye la auditoría de los originales de la corrida independiente.

### Artefactos y límites

`baseline.py` publica CSV y referencias; `train.py` publica modelo JSON, CSV
train/validación e informe; `score.py` aplica el modelo congelado sin entrenamiento
y publica `icc_indice.csv` con componentes, motivos y flags. Nunca reemplazan
`features/.../v3.0/icc.csv`. Salidas4.0 inmutables: un rerun idéntico es idempotente;
un cambio exige otro directorio. Bundle atómico y hashes de archivos.

El índice sigue siendo descriptivo: stock no es acceso individual ni oferta;
TNA UVA y saldo PH son poblaciones distintas. Reconstrucción no es accuracy.
No hay etiquetas supervisadas, test intacto ni vintages. Retrospectiva se aplica
solo después de cerrar la decisión. Reserva desde julio2026 sin puntuar. Uso
operativo diferido hasta un protocolo separado con ≥12 nuevos meses completos
no usados en selección. IAP/IEF conservan su plan, sin entrenamiento en este paso.

### Revisión temporal D21 — 6 de octubre de 2026

La ampliación es por meses consecutivos de calendario, sin shuffle y sin
superponer train/validación. No surge de una búsqueda de cortes con mejor score.
Reduce validación de 24 a 22 meses; el bloque retrospectivo 2024–junio 2026 se
conserva en 30. Los datos de enero/febrero de 2022 dejan de ser validación para
el protocolo nuevo. Los artefactos nominales históricos mantienen sus cortes
originales; no se reescribe aquel experimento. Features y fuentes no cambian,
por lo que el `icc.csv` 3.0 existente sigue vigente. El diagnóstico de baseline
se versiona 3.1 y publica los cortes efectivos en `--check-only`.

## 10. Análisis factorial — experimento 4.1, D23

Se implementa el candidato acordado en la conversación, sin buscar alternativas
hasta obtener aprobación. Reutiliza exactamente las referencias de S1, R/g3/r,
transformaciones Y, media/std poblacional de train y los cortes D21. Train60,
validación22 y retrospectiva30. La validación ya utilizada en PCA convierte la
comparación entre métodos en **exploratoria**, sin test intacto nuevo.

### Especificación anterior a la corrida

`FactorAnalysis(n_components=1, svd_method="lapack", rotation=None, tol=0.01,
max_iter=1000, noise_variance_init=None)`. LAPACK evita aleatoriedad en SVD.
Sin rotación, búsqueda ni cambios de tolerancia para obtener aceptación. Se
captura `ConvergenceWarning`: falta de convergencia o factor no variable bloquea
sustitución. Modelo de señales comunes gaussianas y ruido diagonal propio;
no identifica causalidad ni explica por sí mismo accesibilidad económica.

Cargas generativas L y ruido propio ψ describen Z≈μ+fL+ε. El factor aplicado
es la media posterior, **f=(Z−μ)w**, donde
`w=(L/ψ)/(1+Σ L²/ψ)`. No usar L directamente como coeficientes del score ni
normalizarlos como un vector PCA. Orientar L y w con un solo signo global hacia
costo positivo; no abs por columna. Reconstrucción: μ+fL, sin agregar ruido a
la predicción. Comunalidad por señal: L²/(L²+ψ), descriptiva, sin umbral nuevo.

Los mínimos L1 del S1 (volumen20%, costo20%, momentum10%) se comprueban tanto
en cargas L como en pesos efectivos w. Esta adaptación conserva el requisito de
representación de todas las dimensiones cuando cargas y proyección ya no son
el mismo vector. El mapping conserva **100 V sigmoid((f−f₀)/s_f)**, donde sigmoid
es la logística y f₀/s_f se ajustan solo en train con los criterios S1.

Economía,9 sensibilidades de B, reconstrucción (≥10% mejora promedio; ningún
input >25% peor) y saturación (≤10%) conservan sus reglas. Seis perturbaciones
±10% sobre Z, sin reestandarizar: para comparar coseno se llevan los pesos a
Z original con D·w_pert; las cargas generativas se llevan con L_pert/D. Se
exigen coseno≥0,95, rho_val≥0,90, direcciones admisibles y convergencia. FA puede
absorber escalado en ruido/cargas: pasar coseno/ranking no prueba estabilidad
temporal ni compensa la falta de representación de volumen.

Tres variables aportan6 momentos de covarianza y FA1 estima3 cargas +3 varianzas
propias: **0 grados de libertad de covarianza**. No se presenta un test global
confirmatorio de ajuste. El mínimo60 y la autocorrelación siguen limitando la
evidencia. Los controles económicos se reutilizan; que FA los pase no significa
que su factor sea una medida observada de acceso.

### Resultado en el CSV de origen 20261006_231124_214604

FA converge en19 iteraciones. Economía y saturación pasan; nueve sensibilidades
B pasan. Fracciones L1 de cargas: volumen19,28%, costo42,91%, momentum37,81%.
Fracciones L1 de pesos del factor: volumen**7,10%**, costo62,43%, momentum30,47%.
Volumen incumple el mínimo20% en ambos. Las perturbaciones mantienen rho1 y
coseno≥0,99997, pero conservan la dirección inadmisible por representación.

MSE medio de validación mejora13,91%; volumen tiene ratio2,978 y momentum31,029
frente a baseline. Ambos superan1,25. **FA rechazado por dirección, controles
de perturbaciones con dirección y reconstrucción**. No falla convergencia ni
monotonía: no se confunden motivos. El factor estadístico queda como diagnóstico;
`icc_fa_candidato` queda nulo. `icc_indice` conserva baseline S1 y sus112 meses.

### Operación y evidencia

`ml/factor.py` implementa el método y sus controles; `ml/train.py --method
factor_analysis` lo entrena y evalúa, mientras `--method pca` conserva S1. El
default de train sigue siendo PCA para no cambiar silenciosamente comandos.
`ml/score.py --model RUTA_JSON_FA` identifica el schema4.1 y aplica el artefacto
sin fit. Salidas separadas en `modelos_icc/<run>/v4.1/`, sin reemplazar4.0 ni
`icc.csv` de features3.0. La guía vigente es `../LEEME_ICC.md`.

Las24 pruebas FA verifican posterior, reconstrucción, convergencia, signos,
separación temporal, ausencia de fit al scorear, mínimos, reserva, nulos,
reproducibilidad e integridad. Con las94 regresiones S1/evaluador/features:
**118 pruebas**. Originales del último CSV no adjuntos: fuentes reconstruidas
False en esta entrega; la prueba local auditada es otra corrida con mismos
valores y reproduce el diagnóstico. No se habilita scoring de reserva ni uso
operativo, y no se entrena IAP/IEF en esta ampliación.

## 11. PCA2 — diagnóstico 4.2, D24

Se evalúa si comprimir las tres señales en una dimensión explica la pérdida de
información. Se conserva core R/g3/r, referencias S1, Y=[log1p(R/R₀),−r,
asinh(g/s𝗀)] y escala poblacional de train. Mismos60 train y22 validación.
No se adopta un índice nuevo al retener más varianza.

### Especificación previa a la corrida

`PCA(n_components=2, svd_solver="full", whiten=False)`, sin búsqueda. Cada eje
se orienta haciendo positiva su mayor carga absoluta, como convención de
reproducibilidad; no se alteran signos individuales ni se lo etiqueta como
favorabilidad. Std de cada input>10⁻¹² y varianza del segundo eje>10⁻¹² para
publicar dos PCs identificables. No aplicar mínimos L1 de un índice escalar a
cada eje de un plano ortogonal.

Proyección F=(Z−μ)Aᵀ y reconstrucción Z_hat=FA+μ. MSE por input y promedio en
unidades Z de train. PCA1, FA1 y B1 se ajustan sobre los mismos60 meses para
reproducir sus reconstrucciones, sin reabrir decisiones ni usar retrospectiva.
La comparación con1D es descriptiva: mayor dimensionalidad permite retener más
información y no representa idéntica arquitectura.

Comparador2D predefinido: **[V,H]**, H=0,80C+0,20M de S1. Para cada input Z se
ajusta en train una recta con intercepto, V y H, aplicada congelada a validación.
Igual dimensionalidad no implica igual familia/complejidad: V/H son funciones
no lineales predefinidas, PCA es lineal sobre Y. Contrato diagnóstico: mejora
MSE promedio≥10% frente a V/H y ningún input>25% peor. Error del comparador
≤10⁻¹² o diseño sin rango3: inconcluso/fallo. No valida favorabilidad ni redefine B.

Seis perturbaciones±10% de Z, sin reestandarizar. Comparar planos en coordenadas
originales mediante cosenos de ángulos principales (mínimo≥0,95), usando filas
A_pert·D. Comparar reconstrucciones de los tres inputs en val con rho≥0,90 cada
una. No comparar ejes por nombre: signos/rotaciones pueden variar conservando
el plano. No existe ranking ni mapa logístico ICC PCA2 para medir saturación.

### Resultados en la corrida 20261006_231124_214604

Varianza train: PC1 **64,26%**, PC2 **25,99%**, total **90,25%**. Cargas, orden
volumen/costo/momentum: PC1=[0,444942;0,646120;0,620126],
PC2=[0,887529;−0,225615;−0,401734]. PC1 combina las tres señales; PC2 contrasta
volumen con costo/dinámica. No son etiquetas de régimen o acceso.

MSE val: PCA2=4,9398, PCA1=7,2606, FA1=7,2862, B1=8,4632 y V/H2D=4,1296.
PCA2 mejora41,63% el promedio frente a B1, pero momentum tiene error30,679 veces
el de B1. Frente a V/H2D es **19,62% peor** en promedio y el ratio de costo
es1,421 (>1,25). **Falla reconstrucción2D**. Seis perturbaciones pasan: coseno
mínimo0,99054, rho mínima0,94579. Cobertura, identificabilidad y controles de B
pasan. PCA2 recupera volumen: MSE0,2122 frente a7,8398 de PCA1.

Esto evidencia mejora de representación en estas particiones. La validación
ya usada hace exploratoria la comparación; no aparece un test intacto nuevo.

### Publicación y agregación pendiente

`train.py --method pca2` publica modelo JSON diagnóstico, CSV train/val e informe
en4.2. `score.py --model RUTA_MODELO_PCA2` aplica PCs y B congelados a la
retrospectiva después de cerrar diagnóstico, sin fit. `pc1_diagnostico` y
`pc2_diagnostico` son adimensionales. **`icc_indice` sigue siendo B**, con
`metodo_elegido=baseline_s1`, `indice_pca2_definido=False`. Reserva sin PCs ni
score. Se preservan4.0/4.1 y la matriz de features3.0.

No sumar PCs ni ponderarlas automáticamente por varianza. Para un ICC PCA2 falta
una agregación escalar económicamente interpretable, comprobada con los
criterios económicos existentes, cuyo ajuste use train y no elija pesos por
validación. El diagnóstico no adopta esa regla ni aprueba un ICC ML. Sus fallos
tampoco prueban que toda representación2D o toda agregación sean inviables.

Se agregaron23 pruebas PCA2: proyección/inversa contra scikit-learn, invariancia
de planos, mínimos, temporalidad, comparadores congelados, reserva, scoring sin
fit e integridad. Con las118 anteriores: **141 aprobadas**. Repetición CLI
idéntica, entrada original preservada y ZIP íntegro. Procedencia independiente
mantiene fuentes reconstruidas=False; integración auditada usa otra consolidación
con mismos valores. Guía: `../LEEME_ICC.md`.
