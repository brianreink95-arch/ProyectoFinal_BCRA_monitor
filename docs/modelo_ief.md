# Isolation Forest IEF 0.1

Entrenamiento, referencia congelada, puntuación y comparación implementados.
El módulo es `ml/isolation_ief.py`. La matriz tratada 0.2 y el baseline 0.1
se consumen como bundles existentes, verificados por hashes y reconstrucción
idéntica. Su código y archivos permanecen sin modificaciones.

## Qué se ajustó

Se entrenó exclusivamente con las **875 filas elegibles de train**, correspondientes
a 98 empresas entre noviembre de 2024 y julio de 2025. El bloque train comienza
en agosto de 2024, pero los tres primeros meses solo aportan historia.
Los seis predictores y su orden son los de `features_ief.md`: crecimiento real
logarítmico, cambio de acreedores, HHI, situación máxima, proporción de deuda en
situación ≥2 y cambio trimestral de esa proporción.

Parámetros fijados en el plan:

```python
IsolationForest(
    n_estimators=300, max_samples="auto", max_features=1.0,
    contamination="auto", bootstrap=False, random_state=42, n_jobs=1,
)
```

`max_samples="auto"` toma 256 filas por árbol en esta corrida. No se ajustan
scalers ni imputadores y no se usan CUIT, nombres, tamaño absoluto, grupo,
subsector o etiquetas futuras como predictores. Las fechas y splits se
comprueban contra el protocolo; no se puede reetiquetar validación como train.

El modelo se aplicó a las 587 filas elegibles de validación y las 585 de
evaluación retrospectiva, sin fit ni recalibración. También se distribuyen sus
scores in-sample de train, identificados como tales. Las 353 filas no elegibles
permanecen con motivos originales, scores, posiciones y participaciones nulos.

## Score, escala y ranking

La anomalía cruda es `-estimator.score_samples(X)`: un valor mayor significa
mayor rareza según el bosque. No se usa `predict` para declarar un porcentaje
de empresas problemáticas. `contamination="auto"` no estima prevalencia real.

La referencia es el vector ordenado de 875 anomalías de train. Para un valor s:

```text
percentil_train(s) = 100 * (cantidad_referencia_menor + 0.5 * cantidad_referencia_igual) / 875
```

La mitad de la masa empatada hace explícito el tratamiento de iguales. Un
valor menor que todos los de train recibe 0; uno mayor que todos recibe 100.
La referencia no cambia al puntuar nuevos lotes. Estos extremos de escala no
equivalen a ausencia o certeza de deterioro. La escala puede saturarse.

El orden mensual usa la anomalía **cruda**, evitando crear empates artificiales
entre valores distintos que saturen en 100. Se conservan intervalos de posición
y participaciones fraccionales top 5/top 10, como en el baseline. No se
desempata por CUIT o razón social ni se redondean scores antes de ordenar.

## Comparación y diagnósticos

Coincidencia top-k: suma de los mínimos de las participaciones de ambos métodos,
dividida por `min(k, cantidad_elegible_del_mes)`. La comparación se hace sobre
las mismas filas y se promedian los meses con ranking. Se conserva cada mes en
el JSON, incluyendo los tres meses sin score. Esto mide solapamiento de señales,
no precisión predictiva.

Spearman frente al baseline compara la anomalía cruda con el negativo del
punto medio del intervalo de posiciones del baseline. Los empates permanecen
visibles. Frente a otros bosques se correlacionan anomalías crudas del mismo mes.

| Bloque | Filas puntuadas | Spearman mensual medio con baseline | Coincidencia top 5 |
| --- | ---: | ---: | ---: |
| Train, in-sample | 875 | 0,3486 | 78,06% |
| Validación | 587 | 0,3952 | 80,07% |
| Evaluación retrospectiva | 585 | 0,4196 | 86,67% |

Se aplicaron las sensibilidades predefinidas, sin seleccionar otra configuración:

| Contraste en validación | Spearman mensual medio | Coincidencia top 5 |
| --- | ---: | ---: |
| Semilla 42 vs. 43 | 0,9926 | 93,33% |
| Semilla 42 vs. 44 | 0,9938 | 96,67% |
| Crecimiento logarítmico vs. porcentual original | 0,9680 | 96,67% |

El principal sigue siendo logarítmico, semilla 42. Los tres bosques auxiliares
se ajustan solo en train y no se guardan; se conservan sus métricas completas.
La correlación entre situación máxima y proporción en situación ≥2 es 0,9998
en train: existe redundancia casi total en sus rangos. La composición del top 5
por situación y por signo de crecimiento se reporta como descripción, nunca
como importancia de variables o contribución causal.

En julio de 2026, el modelo coloca primero a Vicentin, luego a Granja Tres
Arroyos, Molino Cañuelas, Manisur y la cooperativa de hongos Aldea. Son anomalías
relativas al panel de entrenamiento, no un ranking integral de solvencia.
El detalle está en `informe_ief.md` y `scores_ief.csv` dentro del bundle.

## Artefactos y aplicación sin fit

```text
data_analytics/modelos_ief/20261006_231124_214604/bosque_v0.1/
  modelo_ief.joblib
  scores_ief.csv
  protocolo_resultados.json
  informe_ief.md
```

El artefacto guarda estimador, parámetros, orden de features, referencia de
train, claves y fingerprint de ajuste y versiones. El JSON registra hashes
del artefacto, scores, insumos y código, más las métricas y el alcance pendiente.
Antes de deserializar un bundle propio, se verifica hash del modelo y versiones
de Python, NumPy, pandas, scikit-learn, joblib y scipy; la aplicación no refitea.
La serialización joblib requiere un artefacto de procedencia confiable y un
entorno compatible. La referencia distribuida usa Python 3.12, pandas 2.2.3,
NumPy 2.3.5, scikit-learn 1.8.0, joblib 1.5.3 y scipy 1.17.0.

Desde la raíz del proyecto, para reconstruir el experimento completo:

```bash
python ml/isolation_ief.py entrenar
```

Los bundles son inmutables. Para una reproducción independiente:

```bash
python ml/isolation_ief.py entrenar --output-dir reproduccion_ief/bosque
python ml/isolation_ief.py puntuar --model-dir reproduccion_ief/bosque --output-dir reproduccion_ief/score
python -m unittest docs.validar_modelo_ief docs.validar_ief -q
```

`puntuar` publica solo el CSV y `protocolo_score.json`. Con los mismos insumos,
su CSV coincide byte a byte con el del entrenamiento. No se distribuye una
copia adicional de esos scores porque se regenera desde el modelo guardado.
El comando protege fuentes y bundles existentes y publica por carpeta atómica.

## Interpretación y trabajo pendiente

Las señales coinciden en gran medida con deterioro ya informado. La estabilidad
numérica y el solapamiento no demuestran capacidad de anticipación ni utilidad
incremental frente al baseline. Las dos variables de situación casi redundantes
limitan la lectura multivariada. El train contiene situaciones adversas: no se
supone una muestra certificada de normalidad.

El panel es intencional, sectorial y retrospectivo; las filas repiten empresas.
El conjunto completo ya fue explorado y no hay un test histórico intacto ni
disponibilidad contemporánea verificada. Los puntajes no son probabilidades
de default, clasificaciones oficiales ni un índice de estrés validado.

Quedan pendientes el contraste exploratorio t+1 con denominadores explícitos,
el holdout por grupos, las seis fichas y revisión humana de casos y el notebook
con gráficos para el informe. No se modifica la configuración para favorecer
resultados posteriores ni se habilitan alertas operativas.

## Fuentes técnicas

- [IsolationForest, scikit-learn 1.8](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.IsolationForest.html).
- [Persistencia de modelos, scikit-learn 1.8](https://scikit-learn.org/1.8/model_persistence.html).
- `plan_ief.md`, `features_ief.md` y `baseline_ief.md`: decisiones del proyecto.
