# Actualización del ICC para VS Code

Se integraron las entregas de S1, PCA1, análisis factorial, PCA2, hipotecarios
empresariales y cierre de las otras series hasta el 15 de octubre de 2026.
El resultado son siete ICC particulares experimentales. Se agregó la matriz
real y tratada 0.2 de Base C: `ml/ief.py` y `docs/features_ief.md`. El baseline IEF está implementado (`ml/baseline_ief.py`). El bosque IEF también está entrenado (`docs/modelo_ief.md`).
El ICC global, IAP, la aplicación web y la habilitación operativa quedan pendientes.

## Cómo abrir el proyecto

Este ZIP contiene el proyecto completo. Extraer su carpeta `proyecto` en un
directorio nuevo y abrirla en VS Code. Instalar el entorno con
`python -m pip install -r requirements_icc.txt`.

Los resultados vigentes están incluidos. Para consultarlos no hace falta
extraer fuentes nuevas ni ejecutar `actualizar_bases.py`.

## Qué abrir primero

| Archivo | Qué resuelve |
| --- | --- |
| `LEEME_ICC.md` | Mapa breve y comandos. |
| `docs/plan_ml.md` | Estado completo y decisiones hasta el 15 de octubre. |
| `docs/criterios_datos.md` | Fórmula S1, referencias y controles del piloto PH. |
| `docs/validacion.md` | Comprobaciones de esta integración. |
| `experimentos/icc/hipotecarios_empresariales_v02/cierre_pesos_icc_v02.md` | Cierre de pesos de PyMEs y No PyMEs. |
| `experimentos/icc/series_v01/informe_cierre_series_icc.md` | Cierre de personales, prendarios, tarjetas y restantes series. |

Los cuatro notebooks de `analisis/` ya estaban en el proyecto original y
conservan sus resultados guardados. Su EDA es anterior a estas extensiones.

## Estado por segmento

Los pesos corresponden a costo y momentum dentro de `100 V (peso C + peso M)`.
Cada segmento tiene referencias y limitaciones propias; sus niveles no son
directamente comparables ni se deben promediar para fabricar un global.

| Segmento | Serie | Costo y momentum | Salida que corresponde revisar |
| --- | --- | --- | --- |
| Hipotecarios personas humanas ML | 927 | 80/20 | `data_analytics/modelos_icc/20261006_231124_214604/v4.0/score_d924e7b7f0e103d3c748/icc_indice.csv` |
| Hipotecarios PyMEs ML | 935 | 60/40 | `experimentos/icc/hipotecarios_empresariales_v02/resultados/icc_935_v02.csv` |
| Hipotecarios No PyMEs ML | 936 | 80/20 | `experimentos/icc/hipotecarios_empresariales_v02/resultados/icc_936_v02.csv` |
| Prendarios personas humanas ML | 960 | 50/50 | `experimentos/icc/series_v01/resultados/indices/icc_960.csv` |
| Prendarios PyMEs ME | 979 | 50/50 | `experimentos/icc/series_v01/resultados/indices/icc_979.csv` |
| Personales sector privado ML | Clave local finserprom | 60/40 | `experimentos/icc/series_v01/resultados/indices/icc_finserprom_personales_ml_privado.csv` |
| Tarjetas sector privado ME | Clave local finserprom | 60/40 | `experimentos/icc/series_v01/resultados/indices/icc_finserprom_tarjetas_me_privado.csv` |

Además se conservan nueve indicadores parciales de volumen y dinámica, siete
series de contexto y una diferida. Los parciales no son ICC completos.
La decisión global se encuentra en
`experimentos/icc/series_v01/resultados/decision_global.json`.

## Código esencial

`ml/features.py` prepara las variables del piloto. `ml/baseline.py` ajusta
referencias S1 en train. `ml/train.py` evalúa el candidato solicitado;
`ml/factor.py` y `ml/pca2.py` implementan las dos extensiones estadísticas.
`ml/score.py` aplica el artefacto explícito sin reajustarlo.

PCA1 y FA1 no fueron admitidos. PCA2 es un diagnóstico sin regla escalar
aprobada. El puntaje del piloto continúa siendo S1.

Las extensiones permanecen en `experimentos/icc/` porque fueron entregadas como
paquetes autónomos con fuentes congeladas. Se incorporaron al proyecto con sus
scripts y pruebas; no se reemplaza el piloto PH con el código empresarial ni se
presentan como parte de una API o ejecución global ya implementada.

## Reproducir el piloto

Entorno verificado: Python 3.12, pandas 2.2.3, numpy 2.3.5 y scikit-learn 1.8.0.
Ejecutar desde la raíz del proyecto usando ese entorno:

```powershell
python -m pip install -r requirements_icc.txt
python ml/baseline.py --check-only
python -m unittest docs.validar_features_icc_v3 docs.validar_evaluate_features docs.validar_icc_s1 docs.validar_icc_factor docs.validar_icc_pca2 -q
```

Los resultados generados desde los datos locales ya vienen incluidos. Para una
nueva reproducción elegir otro directorio de salida, porque los bundles son
inmutables. Por ejemplo:

```powershell
python ml/train.py --method pca --output-dir reproduccion_icc/pca
python ml/score.py --model reproduccion_icc/pca/modelo_icc.json --output-dir reproduccion_icc/score
```

Usar `--method factor_analysis` o `--method pca2` con destinos diferentes para
repetir esos experimentos. PCA2 publica `modelo_pca2.json`.

## Comprobar las extensiones

Cada comando se ejecuta desde la carpeta indicada:

| Carpeta | Comando |
| --- | --- |
| `experimentos/icc/hipotecarios_empresariales_v01` | `python -m unittest validar_empresariales -v` |
| `experimentos/icc/hipotecarios_empresariales_v02` | `python -m unittest validar_cierre -v` |
| `experimentos/icc/series_v01` | `python validar.py` |

Para recalcular las otras series desde sus fuentes congeladas, ejecutar en
`experimentos/icc/series_v01`:

```powershell
python ejecutar.py --fase todo --output resultados_reproduccion
python validar.py --output resultados_reproduccion
```

## Evidencia y salidas regenerables

La reproducción canónica del piloto está en `data_analytics/modelos_icc/`.
Solo se conserva una consolidación ABC y su matriz de features vigente.
Los modelos rechazados permanecen para justificar las decisiones metodológicas.

La comparación de pesos previa a 0.2 sigue en
`experimentos/icc/pesos_empresariales_v01/`, usando los candidatos empresariales
compartidos. La evaluación empresarial 0.1 usa los módulos `ml/` centrales y
snapshots idénticos de `experimentos/icc/series_v01/fuentes/`.
Los paquetes de experimentos se ejecutan dentro de este proyecto completo.

Las trayectorias de las 42 combinaciones serie/peso de otras series se regeneran
con `ejecutar.py --fase todo`; no se distribuyen como 42 CSV repetidos.
Los 28 JSON de controles se consolidaron en
`experimentos/icc/series_v01/resultados/controles_escenarios.csv`.
Se conservan todas las métricas de sensibilidad y contraste ECC, los cuatro
índices admitidos, los nueve parciales y sus referencias.

Para la entrega inmediata, revisar los informes, los siete CSV vigentes y los
notebooks. El informe de depuración explica la selección de archivos.
