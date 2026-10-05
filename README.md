# Observatorio de Financiamiento y Endeudamiento

Proyecto Final — Licenciatura en Ciencia de Datos, CAECE.

El proyecto organiza datos del BCRA como **tablas de una futura base relacional**.
Por ahora se guardan en CSV; no hace falta instalar SQLite ni otro motor.
El pipeline genera 12 tablas con tipos, claves y relaciones validadas, todas
asignadas a un consumidor del proyecto. Ya se construye una primera matriz de
features ICC para hipotecarios ML a personas humanas. Los modelos, scores y las
features de IAP/IEF siguen pendientes; todavía no se entrenan ni se publican índices.

## Ejecutar

Instalar desde esta carpeta:

```bash
python -m pip install -r requirements.txt
```

Actualizar fuentes de las tres bases y reconstruir sus tablas:

```bash
python actualizar_bases.py --extract a b c
```

Actualizar solo las ofertas B y consolidar las tres bases:

```bash
python actualizar_bases.py --extract b
```

Reconstruir las tablas a partir de fuentes guardadas, sin red:

```bash
python actualizar_bases.py
```

Cada ejecución publica una carpeta nueva en `data_analytics/runs/`.
`data_analytics/latest.json` identifica la última consolidación ABC completa.
No concatenar corridas: son versiones del estado de las tablas, no particiones
independientes. La entrega incluye solo la versión vigente. Su fecha es la de
transformación; las fuentes incluidas fueron adquiridas en septiembre de 2026.

## Tablas e índices

| Base | Tablas que se exportan | Uso previsto |
|---|---|---|
| A | `series`, `observaciones` | ICC: condiciones crediticias y momentum. Contexto de IAP/IEF cuando se pueda alinear temporalmente. |
| B | `entidades`, `snapshots`, `ofertas` | IAP: atractivo de productos y comparador. Contexto de oferta para ICC. |
| C | `empresas`, `subsectores`, `empresa_subsector`, `acreedores`, `consultas`, `deuda_entidad_mes`, `empresa_mes` | IEF: estrés empresarial, fichas y comparación por subsector. |

No se exportan fotografías duplicadas, pivots mensuales, paneles repetidos por
subsector ni matrices de transición. Se calcularán en features/EDA cuando un
consumidor los requiera. Los controles de calidad adicionales se registran en
`run_metadata.json`. Las capturas incompletas B y los resultados de consulta C
sí son tablas porque gobiernan elegibilidad y cortes temporales.

La adquisición nueva de C conserva los maestros usados, cobertura y deuda
fuente; ya no genera el antiguo target exploratorio, paneles intermedios ni
ZIPs duplicados. Los artefactos históricos se conservan íntegros para reproducir
los cuatro notebooks finales.

## Diseño y siguiente etapa

- [Diseño de tablas](docs/diseno_tablas.md): grano, PK/FK, diccionario, unidades,
  disponibilidad, consumidores por índice y tratamiento de las salidas anteriores.
- [Plan de ML](docs/plan_ml.md): features por índice, baselines, modelos iniciales,
  cortes temporales, evaluación, criterios de avance y orden de implementación.
- [Contrato ejecutable](config/esquema_tablas.json): columnas, tipos, nulabilidad,
  claves y asignación ICC/IAP/IEF. El exportador verifica el contrato antes de escribir.
- [Validación](docs/validacion.md): evidencia de esta entrega y límites de las pruebas.

### Features ICC — implementado

[Diccionario ICC](docs/features_icc.md): seis features de crédito nominal,
TNA sobre UVA, composición por destino y volatilidad para el agregado
**hipotecarios ML a personas humanas**, no para todo el crédito argentino.
Una fila es un mes; las filas no elegibles conservan indicadores y motivos.
La tasa UVA es un proxy parcial, no el costo promedio del agregado.

```bash
python ml/features.py
```

Lee solo A de la última consolidación ABC completa, sin red. Escribe una matriz
única en `data_analytics/features/<run_origen>/icc.csv`, fuera de las 12 tablas.
Origen actual: `20261005_011327_837742`; 321 meses (1999-12–2026-08), de los
cuales **119 son elegibles (2016-08–2026-06)**. Julio/agosto de 2026 permanecen
sin stock; no se imputan. La salida registra hashes, versión y cutoff de referencia.
La evaluación futura será retrospectiva, no point-in-time sin vintages.

### Splits y baseline hipotecario — implementado, experimental

```bash
python ml/baseline.py
```

Consume la matriz ICC persistida y compara tres referencias de percentiles,
ajustadas **solo en train**: trimestral, mensual y balanceada por dimensión
(50% crecimiento nominal, 50% condiciones de tasa UVA). Composición y volatilidad
se conservan como descriptores con peso cero; no se borran automáticamente.

Cortes fijos: **65 meses train (2016-08–2021-12)**, **24 de validación
(2022–2023)** y **30 de evaluación retrospectiva (2024–2026-06)**. Este último
bloque ya fue inspeccionado: **no es test final intacto**. Desde 2026-07 se
reserva sin puntuar, aunque futuras filas resulten elegibles.

Outputs con consumidor: `data_analytics/baselines/<run_origen>/icc_hipotecario.csv`
para comparar variantes y `protocolo_icc.json` para reproducir splits/referencias.
No son un ICC nacional, score validado ni salida web. Ver [diccionario y protocolo](docs/features_icc.md).

La metodología BCRA puede arrastrar saldos: `stock_observado` confirma publicación,
no actualización contemporánea. La tasa UVA pondera otorgamientos al sector
privado; el stock mide saldos PH. Los extremos de 2024 coinciden con fuentes,
pero su causa sigue pendiente; no se corrigen ni eliminan. En validación, 18/24
tasas quedan fuera del rango de train: revisar saturación antes de un modelo.

Antes de entrenamiento faltan revisión económica/metodológica y protocolo de
estabilidad/test verdaderamente no inspeccionado. `ml/train.py`, `ml/score.py`,
PCA, IAP e IEF no están implementados. No se añaden dependencias ni scripts vacíos.

## Archivos y carpetas

La raíz mantiene seis archivos: `base_a.py`, `base_b.py`, `base_c.py`,
`actualizar_bases.py`, `requirements.txt` y este README.

Cada base contiene secciones de configuración, extracción, transformación y CLI.
`python base_a.py` extrae y transforma una sola base; `--offline` solo transforma;
`--extract-only` solo adquiere. Las mismas opciones aplican a B y C. Usar `--help`
para rutas y opciones. Las corridas individuales tienen su propio puntero y no
reemplazan el estado ABC completo. No se necesita un lanzador PowerShell.

| Carpeta | Función |
|---|---|
| `config/` | Contrato de tablas, catálogo A y maestro C. El XLSX es un único insumo editable del maestro; las tablas de salida son CSV. |
| `data_a/`, `data_b/`, `data_c/` | Fuentes, respuestas y registros de adquisición para auditoría y reproducibilidad. No son el esquema relacional de consumo. |
| `data_analytics/` | Corridas de las 12 tablas relacionales; `features/` contiene la matriz ICC y `baselines/` las referencias experimentales/protocolo por consolidación. |
| `ml/` | Features y baseline experimental ICC hipotecario; modelos, entrenamiento y scoring pendientes. |
| `analisis/` | Cuatro notebooks finales explicativos y sus resultados históricos. |
| `lib/` | Infraestructura común, validación del contrato y adaptador de notebooks. |
| `docs/` | Diseño, plan ML, propuesta académica, inventario y verificaciones. |

Las versiones y exports anteriores están en el ZIP histórico separado. No son
dependencias del proyecto. No se borran ni modifican las fuentes históricas.

## Reglas fundamentales

Preservar IDs como texto, unidades originales, ceros reportados y ausencia de
observación. No mezclar poblaciones/monedas ni sumar subsectores solapados.
Las claves provisionales de ofertas no identifican productos persistentes.
La fecha del dato no equivale a su disponibilidad: el plan distingue análisis
retrospectivo de validación point-in-time. Los índices no son probabilidades de
default ni recomendaciones financieras personalizadas.

Repetir controles desde la raíz:

```bash
python -m unittest docs.validar_baseline_icc docs.validar_features_icc docs.validar_semantica docs.validar_relacional -v
```
