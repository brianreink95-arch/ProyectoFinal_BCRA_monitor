# Validación del ajuste por inflación

5 de octubre de 2026, Buenos Aires. Contrato 2.0.

## Resultado

Se adquirieron los niveles oficiales INDEC nacional, nivel general, base
diciembre de 2016 = 100: **117 meses, diciembre 2016–agosto 2026**. La fuente
declara actualización el 10/09/2026. Se conserva el original, sus metadatos y
la normalización con precisión publicada; enero de 2017 es 101,5859, sin
reconstruirlo desde variaciones mensuales redondeadas.

Los seis stocks ICC (927 y 1145–1149) se contrastaron contra XLS oficiales
BCRA por tipo de titular/destino. **690 comparaciones: 115 meses por serie**,
diciembre de 2016–junio de 2026. Todos coinciden con XLS en miles de ARS / 1000
dentro de 0,5 de redondeo. Se verificó escala **millones de ARS** en la API,
contraria al metadato declarado “miles”. Se conserva evidencia por mes/valor;
la habilitación no se extiende automáticamente a valores revisados o meses
nuevos sin contraste. Ejemplo diciembre de 2016, serie 927: API 37.938;
XLS 37.938.011 miles de ARS. No se modifica el valor original.

La consolidación offline genera **13 tablas** y conserva:

- A: 65 series y 41.687 observaciones; 690 ajustadas, 1.224 anteriores a base
  dentro de los seis stocks seleccionados y 39.773 fuera del alcance del ajuste.
- B: 46.586 ofertas, 370 entidades y 14 snapshots (13 completos). Sin ajuste
  monetario automático; TEA/CFTEA y demás columnas conservadas.
- C: 100 empresas, 102 pertenencias, 28.968 registros empresa-acreedor-mes
  ajustados y 2.400 empresa-mes ajustados. Reconciliación constante por empresa-mes.

Una comparación de todas las columnas de hechos y dimensiones originales con
la entrega relacional anterior confirmó igualdad en valores, orden y cantidad
de filas. La dimensión `series` añade criterios/unidades y modifica solamente
las notas/validación de los seis stocks contrastados. Las fuentes A/B/C
anteriores conservaron sus hashes; los nuevos caches se añaden sin alterar ellas.

## Pruebas ejecutadas

**40 pruebas aprobadas:** 26 de inflación/integración, 8 relacionales y 6 de
semántica C. Cubren fórmula y crecimiento real, base 100, precisión nacional,
ceros/huecos, unidades no habilitadas, exclusión de tasas, conservación de
ratios, duplicados, índice inválido/cambio de base, calendario incompleto,
mes no publicado, referencias, nominales, universo C y reconciliación.

Se comprobaron además dos consolidaciones reproducibles con iguales hashes
en sus 13 CSV, red bloqueada en transformación offline, corrida individual C
sin extraer A, fallo de IPC sin publicación de puntero y staging A con cache
propio/restauración ante fallo simulado. Las ocho pruebas relacionales validan
PK/FK, formatos y conservación de ofertas; las seis semánticas verifican que
ausencia, saldo cero y situaciones desconocidas siguen diferenciadas.

Se descargó INDEC en vivo y se analizaron los originales BCRA descargados.
No se recapturaron las 65 historias BCRA, todas las ofertas ni las 100 empresas:
la consolidación usa las fuentes guardadas. La extracción A completa se
validó en staging con adquisición simulada y transformador real; no se declara
probada de extremo a extremo contra todas las APIs en vivo. No se entrenó ML.

Entorno de validación: Python 3.12, pandas 2.2.3; Windows/Python 3.14.6 no
se ejecutaron aquí. No se reejecutaron todos los gráficos EDA.

## Instalar y reproducir

Este ZIP es una **actualización para el proyecto existente**, no contiene otra
copia de todos los datos históricos. Copiar su contenido sobre la raíz del
proyecto, aceptando el reemplazo de los archivos incluidos. Se incluye el cache
IPC/unidades y una consolidación válida bajo `data_analytics/`; las corridas
anteriores se conservan. No incluye ni reemplaza `ml/`, `docs/features_icc.md`,
`docs/plan_ml.md`, protocolos, notebooks ni capturas A/B/C históricas.

Desde la raíz:

```bash
python -m pip install -r requirements.txt
python actualizar_bases.py
python docs/validar_inflacion.py
python docs/validar_relacional.py
python docs/validar_semantica.py
```

Actualizar únicamente IPC y consolidar:

```bash
python actualizar_bases.py --refresh-ipc
```

Si hay valores revisados o meses ICC nuevos pendientes de contraste:

```bash
python base_a.py --audit-units-only
python actualizar_bases.py
```

La extracción normal A actualiza BCRA, IPC y auditoría de unidades en staging.
Un desajuste con los XLS oficiales detiene esa adquisición para revisión;
no se sobreescribe el cache anterior con datos inconsistentes.

## Continuación

Los criterios se mantienen en `docs/criterios_datos.md`. Actualizar las
referencias a este documento desde `docs/features_icc.md` y `docs/plan_ml.md`.
El feature engineering ya consume `valor_constante_dic2016` para crecimiento y
volatilidad de stocks; mantiene tasas y participaciones bajo su interpretación
original. La matriz ICC 2.0 y sus fórmulas fueron verificadas.

La primera fila elegible es junio de 2017 y, con train hasta diciembre de 2021,
quedan **55 meses**, por debajo del mínimo congelado de 60. El baseline real queda
bloqueado: no se redujo el mínimo ni se movieron cortes. Resolver y documentar ese
criterio antes de recalibrar. El baseline nominal anterior se conserva como
experimento histórico y no se aplica a features reales.
El ajuste no resuelve arrastre de saldos fuente, revisiones, representatividad ni
disponibilidad histórica.
