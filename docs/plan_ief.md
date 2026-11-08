# Plan de modelado de la Base C

Primera versión del módulo IEF empresarial. Plan fijado el 21 de octubre de 2026.
Este documento define el experimento y registra su avance. El modelo principal ya está entrenado.
La etapa 1 y el tratamiento 0.2 están implementados y verificados: ver `features_ief.md`.
Se confirmaron 2.400 filas y 2.047 elegibles con deuda real en ARS.
La etapa 3 está implementada: `baseline_ief.md`. El bosque 0.1 está entrenado
y comparado con el baseline, con referencia congelada, estabilidad y sensibilidad:
`modelo_ief.md`. Continúan pendientes el contraste t+1, los grupos y la revisión de casos.

## Objetivo y alcance de la primera entrega

Implementar un detector de perfiles crediticios empresariales atípicos mediante
Isolation Forest, compararlo con una referencia interpretable y presentar sus
resultados retrospectivos en el informe final. La unidad es una empresa por mes.
El producto será un puntaje de anomalía acompañado por las señales crediticias
observables que ayudan a interpretarlo.

La primera entrega se concentra en un baseline y un modelo. El puntaje no se
interpreta como probabilidad de default ni se presenta como un índice de estrés
validado. La conclusión puede ser que el modelo detecta rarezas pero no aporta
información adicional suficiente frente al baseline. Ese resultado también debe
documentarse. No se incorporarán B, otras familias de modelos, un global ni la
aplicación web durante este experimento.

## Datos comprobados antes de definir el experimento

Fuente: proyecto depurado, consolidación 20261006_231124_214604.

| Elemento | Situación observada |
| --- | --- |
| Empresas | 100 personas jurídicas de Agroindustria. |
| Calendario | Agosto de 2024 a julio de 2026, 24 meses. |
| Panel empresa y mes | 2.400 filas; todos los meses están observados. |
| Deuda por entidad y mes | 28.968 filas. |
| Meses con deuda activa | 2.353. |
| Meses sin deuda activa | 47; se conservan y quedan sin score en esta versión. |
| Revisión y proceso judicial | Sin variación: falsos en las 2.400 filas. |
| Deterioros descriptivos en el mes siguiente | 37 sobre 2.245 pares consecutivos con situación activa conocida. |

Las 2.400 filas no son observaciones independientes. El panel es intencional,
sectorial y no representa probabilísticamente a todas las empresas argentinas.
Los datos provienen de capturas retrospectivas, sin vintages históricos
contemporáneos verificados. Los resultados no demostrarán predicción operativa.

## Etapa 1 Preparar una matriz pequeña y trazable

Consumir las tablas relacionales existentes: empresa_mes, deuda_entidad_mes,
empresas, consultas y empresa_subsector como contexto. No repetir la ingesta.
La pertenencia a varios subsectores no duplica filas de entrenamiento.

El core inicial tendrá seis variables:

| Variable propuesta | Construcción y uso |
| --- | --- |
| Crecimiento real de deuda a tres meses | 100 por deuda real actual dividida por deuda real de tres meses antes, menos uno. Exige denominador positivo y calendario observado completo. |
| Cambio de acreedores activos a tres meses | Diferencia del número de acreedores con saldo positivo. No necesita identificar altas y bajas por nombres de bancos. |
| Concentración HHI | HHI de saldos positivos del mes. Es un descriptor de concentración, no riesgo automático. |
| Situación máxima activa | Máxima situación entre las financiaciones con saldo positivo. |
| Porcentaje de deuda en situación 2 o superior | Suma de las proporciones de situación 2 y situación 3 o superior. |
| Cambio de esa proporción a tres meses | Diferencia en puntos porcentuales; no una tasa relativa con denominador cero. |

Usar deuda en miles de pesos de diciembre de 2016 para construir su crecimiento.
Los lags se calculan sobre la grilla mensual por CUIT; no se comprimen huecos.
No imputar observaciones ni dividir por cero. Una entrada a deuda después de un
cero reportado se registra como evento y puede quedar sin crecimiento utilizable.
La falta de score conserva un motivo explícito; no equivale a normalidad.

El saldo absoluto, la razón social, el CUIT, los subsectores y el grupo económico
se conservan como contexto, no como predictores iniciales. Se evita así que la
primera señal quede dominada por tamaño o identificadores. Las señales legales
constantes y la proporción de situación desconocida, también constante en los
meses activos de esta captura, quedan fuera del core. Las columnas constantes
adicionales se detectarán y documentarán usando train exclusivamente.

La auditoría preliminar de estas seis variables arroja 875 filas elegibles en
train, 587 en validación y 585 en evaluación. La implementación debe reproducir
esos conteos o explicar cualquier diferencia antes del ajuste.

## Etapa 2 Fijar la separación temporal

| Bloque | Fechas de los meses | Función |
| --- | --- | --- |
| Train | Agosto de 2024 a julio de 2025 | Calcular features disponibles, ajustar el bosque y referencias del score. Los primeros tres meses sirven de historia y no son elegibles para todo el core. |
| Validación | Agosto de 2025 a enero de 2026 | Revisar cobertura, estabilidad y casos con el modelo ya ajustado. |
| Evaluación retrospectiva final | Febrero de 2026 a julio de 2026 | Publicar el resultado de la configuración congelada; no volver a ajustar con estos meses. |

Mantener todas las empresas de un mes en el mismo bloque. Las ventanas pueden
usar observaciones anteriores al corte como historia; no pueden usar meses
posteriores a la fila que se puntúa. Las empresas pueden repetirse entre bloques
porque el objetivo principal es monitorear un panel conocido. Esto no demuestra
generalización a empresas nuevas.

La evaluación final es fuera del ajuste, pero no un test histórico intacto:
el conjunto completo ya fue explorado. No usar shuffle ni recalibrar el score
con cada nuevo mes. El experimento no se extiende automáticamente a otros datos.

## Etapa 3 Baseline interpretable implementado

Ejecución: `python ml/baseline_ief.py`. Ver `baseline_ief.md` para columnas,
tratamiento de empates, cobertura y ejemplos. El módulo consume la matriz 0.2
congelada sin cambiar el código ni las referencias de tratamiento.

Usar una prioridad lexicográfica descendente:

1. situación máxima activa;
2. proporción de deuda en situación 2 o superior;
3. aumento positivo de esa proporción a tres meses.

Publicar esos tres componentes y el orden resultante. Este baseline resume
señales crediticias informadas; no necesita pesos ajustados ni un score artificial
de 0 a 100. Los empates se mantienen visibles. En comparaciones top-k se usará
ponderación fraccional de los empates en el borde, evitando aparentar diferencias
por ordenar alfabéticamente empresas.

## Etapa 4 Isolation Forest entrenado

Implementado en `ml/isolation_ief.py`; se ajustó exclusivamente con 875 filas
de train, sin optimizar parámetros. La aplicación desde el artefacto no hace
fit. Los resultados y limitaciones se documentan en `modelo_ief.md`.

Configuración inicial fija para scikit-learn 1.8.0:

```python
IsolationForest(
    n_estimators=300,
    max_samples="auto",
    max_features=1.0,
    contamination="auto",
    bootstrap=False,
    random_state=42,
    n_jobs=1,
)
```

Ajustar únicamente con las filas elegibles de train. No introducir un target
supervisado ni escalar o transformar variables usando estadísticas futuras.
El bosque principal consumirá los seis predictores tratados: crecimiento
logarítmico real y las otras cinco variables sin transformar. El crecimiento
porcentual original queda como contexto. La sensibilidad predefinida usará
también un bosque con ese crecimiento original, con los mismos parámetros y
sin seleccionar por resultados de la evaluación final. El diccionario y las
referencias de diagnóstico congeladas de train están en `features_ief.md`. Se comprobará
que las variables discretas y correlacionadas no dominen los casos señalados.

Guardar el modelo ajustado, nombres y orden de features, versiones, parámetros,
fechas y hashes. Usar -score_samples como puntaje continuo, orientado a mayor
anomalía. Para una presentación de 0 a 100, usar el percentil empírico con
tratamiento explícito de empates sobre los scores de train y conservar también
el valor crudo. Esa escala es relativa a la referencia de entrenamiento; puede
saturarse fuera de su rango y no es probabilidad de deterioro.

contamination no estima la proporción real de empresas con problemas. La revisión
de las cinco señales mayores por mes es una capacidad de revisión predefinida,
no una declaración de que el 5% de las empresas sea riesgoso. No buscar parámetros
hasta conseguir una métrica o casos favorables.

## Etapa 5 Evaluar y explicar el resultado

### Evaluación principal

- Cobertura por mes, bloque y empresa, incluyendo motivos de no elegibilidad.
- Distribución y evolución del score; concentración de señales por empresa.
- Estabilidad: repetir los mismos parámetros con semillas 43 y 44, conservando
  42 como modelo principal. Reportar Spearman de scores y coincidencia del top-5
  mensual en validación; no seleccionar la semilla por su resultado.
- Comparación con el baseline: coincidencias y divergencias de las señales.
  Coincidir con mora ya observada es coherencia descriptiva, no utilidad nueva.
- Separar casos atípicos con deterioro informado de cambios benignos, contracción,
  desendeudamiento o concentración estable. No asignar una dirección de riesgo
  automática al crecimiento o al HHI.

### Contraste secundario con deterioro posterior

Derivar un diagnóstico aparte: situación máxima activa en t+1 mayor que en t,
exigiendo meses consecutivos y situación conocida en ambos. No imputar etiqueta
cuando no hay deuda activa o no hay observación posterior; julio de 2026 queda
sin etiqueta t+1. Las etiquetas nunca entran en las features ni en el ajuste.

Reportar eventos y prevalencia en cada bloque y, si existen casos suficientes,
concentración de deterioros en el top-5/top-10 mensual, precision@k y lift frente
al universo elegible y al baseline, con denominadores explícitos. No agrupar el
score de julio como si conociera agosto. Los 37 eventos de todo el panel y sus
repeticiones por empresa limitan la interpretación. Estas métricas son un
contraste exploratorio y no el criterio para aprobar el detector de anomalías.
No se reportará accuracy como prueba principal de calidad.

### Generalización y revisión de casos

Como comprobación secundaria, reservar 20% de grupos registrados con un split
reproducible de semilla 42. Cuando no existe grupo informado, usar CUIT como
unidad; no inferir controladores. Ajustar otro bosque solo con el train temporal
de los grupos restantes y puntuar los grupos reservados en los meses posteriores.
Publicar el número real de empresas/grupos y las métricas de cobertura; este
ejercicio no sustituye la evaluación temporal del panel conocido.

Preparar seis fichas breves por reglas de selección reproducibles: dos señales
altas con deterioro observado, dos altas sin él y dos divergencias fuertes frente
al baseline, sin repetir la misma empresa si hay alternativas. Si una categoría
no tiene casos, declararlo. Cada ficha mostrará trayectoria, deuda real,
acreedores, situación y las features más alejadas de referencias de train.
Esas desviaciones son contexto, no contribuciones causales del bosque.
Brian revisará al menos tres fichas para aportar interpretación económica al
informe y distinguir una alerta útil de una rareza sin tensión crediticia.

## Etapa 6 Generar una entrega compacta

Estado: matriz/tratamiento 0.2 y baseline 0.1 implementados. El baseline usa
un módulo compañero para conservar inmutable la procedencia del tratamiento.
El bosque, sus scores, estabilidad, sensibilidad y comparación descriptiva con el
baseline están implementados. El notebook, t+1, grupos y revisión de casos quedan pendientes.

| Archivo | Función |
| --- | --- |
| ml/ief.py | Matriz y tratamiento 0.2; conserva referencias y procedencia. |
| ml/baseline_ief.py | Baseline mensual 0.1, sin fit y con empates explícitos. |
| ml/isolation_ief.py | Entrenar, guardar, puntuar sin fit y contrastar el bosque 0.1. |
| docs/validar_modelo_ief.py | Train exclusivo, calibración congelada, scoring y persistencia. |
| docs/validar_ief.py | Pruebas de calendario, elegibilidad, ausencia de fuga temporal, scoring y reproducibilidad. |
| analisis/05_modelado_base_c.ipynb | Relato reproducible con método, resultados y gráficos guardados. |
| data_analytics/modelos_ief/<run_origen>/v0.2/ | Matriz tratada y su protocolo. |
| data_analytics/modelos_ief/<run_origen>/bosque_v0.1/ | Modelo, scores, protocolo/evaluación e informe breve. |

Conservar un solo artefacto por función: features_ief.csv, modelo_ief.joblib,
scores_ief.csv, protocolo_resultados.json, casos_revision.csv e informe_ief.md.
El JSON registrará también el hash del modelo. No añadir carpetas duplicadas por
cada semilla: guardar sus métricas en la evaluación; el modelo principal es 42.

Pruebas mínimas: PK CUIT-mes; lags sin comprimir meses; ceros y ausencias distintos;
restricción de train; modificación de datos futuros no cambia features pasadas
ni modelo ajustado; score sin fit; percentiles congelados; situaciones
desconocidas no imputadas; meses sin score conservados; semillas reproducibles.
Ejecutar además las regresiones semánticas y relacionales que corresponden.

## Cómo entra en el template

| Sección | Evidencia que aportará esta implementación |
| --- | --- |
| Metodología | Unidad, universo, seis features, elegibilidad, baseline, Isolation Forest y cortes temporales. |
| Análisis y resultados | Cobertura real; distribución del score; estabilidad; comparación con baseline; contraste posterior y fichas. |
| Discusión | Utilidad incremental, señales benignas, circularidad de la mora observada, grupos, dependencia del panel y límites de las etiquetas. |
| Conclusiones | Qué logró el detector, qué no pudo demostrar y qué requiere observación prospectiva. |
| Apéndice soporte | Script, notebook, datos, artefacto y protocolo reproducible en el directorio accesible de la entrega. |

Gráficos mínimos: distribución de scores por bloque; evolución mensual de
señales/cobertura; comparación modelo-baseline; trayectorias de tres casos.
El informe debe diferenciar el análisis efectuado de cualquier uso operativo
futuro. Un bosque entrenado con resultados negativos o limitados se informa
sin sustituirlo automáticamente por nuevos modelos.

## Orden de trabajo

1. Matriz y tratamiento 0.2 implementados y verificados; resultados y diccionario en `features_ief.md`.
2. Baseline y bosque principal construidos y verificados.
3. Artefacto y referencia de train congelados.
4. Estabilidad, sensibilidad y comparación con baseline ejecutadas. Pendientes:
   contraste t+1, holdout por grupos y revisión de casos.
5. Generar notebook e informe breve; revisar tres fichas con Brian.
6. Ejecutar pruebas y actualizar el ZIP completo con esta versión.

La primera implementación debe priorizar la matriz, baseline, bosque, evaluación
temporal y evidencia para el informe. El contraste por grupos y las fichas deben
documentar cualquier limitación de cobertura; no se ampliará la búsqueda de
modelos para ocultar resultados desfavorables.

## Referencias técnicas

- scikit-learn developers. IsolationForest, documentación 1.8.0.
  https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.IsolationForest.html
- Plan ML vigente del proyecto y tablas de la consolidación
  20261006_231124_214604, Base C.

Las decisiones de features, cortes y revisión son las del experimento propuesto;
la documentación de scikit-learn fundamenta el comportamiento del estimador,
la orientación de score_samples y la función de contamination.
