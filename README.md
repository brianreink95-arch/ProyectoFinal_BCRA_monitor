# Observatorio de Financiamiento y Endeudamiento

Proyecto Final de la Licenciatura en Ciencia de Datos de CAECE.
Integra fuentes públicas del BCRA, conserva su historia y desarrolla una capa
analítica para explorar financiamiento y endeudamiento en Argentina.

**Empezar por [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md)** para conocer el alcance
actual, sincronizar un clon y configurar VS Code. El ZIP incluye código, datos
y resultados de referencia. Para reproducir el ICC, ver [LEEME_ICC.md](LEEME_ICC.md).
La limpieza anterior al modelado de Base C quedó registrada en
[INFORME_DEPURACION.md](INFORME_DEPURACION.md).

## Estado actual

- Las bases A, B y C generan 13 tablas bajo contrato relacional 2.0, incluidos
  el deflactor IPC y sus referencias. Se conservan en CSV.
- Cuatro notebooks de `analisis/` documentan calidad y exploración con sus
  resultados históricos guardados.
- El piloto hipotecario PH incluye features 3.0, baseline S1 4.0,
  entrenamiento/evaluación PCA1 y FA1, diagnóstico PCA2 y scoring reproducible.
  Los candidatos no sustituyeron el baseline S1.
- Se recuperaron los cierres autónomos de hipotecarios empresariales y de las
  restantes series: siete ICC particulares experimentales en total, además de
  indicadores parciales y series de contexto.
- La matriz IEF de Base C está implementada con seis predictores y deuda
  real: 2.047 filas elegibles de 2.400. La versión 0.2 trata el crecimiento
  con logaritmos y fija referencias de diagnóstico solo en train.
  El baseline mensual y el bosque IEF están implementados.
  El bosque se ajustó solo con train; evaluación predictiva y revisión de casos pendientes.
- El ICC global, IAP, la aplicación web y la operación prospectiva están
  pendientes. Los índices son instrumentos descriptivos internos.

## Mapa del proyecto

| Ubicación | Función |
| --- | --- |
| `base_a.py`, `base_b.py`, `base_c.py` | Extraer y transformar cada base. |
| `actualizar_bases.py` | Coordinar la consolidación ABC. |
| `config/` | Contrato de tablas, catálogo A y maestro empresarial C. |
| `lib/` | Lectura, validación, ajuste de precios y soporte compartido. |
| `data_a/`, `data_b/`, `data_c/` | Fuentes y registros de adquisición. |
| `data_analytics/latest.json` | Identificar la consolidación completa vigente. |
| `data_analytics/runs/` | Versiones completas de las tablas; no concatenarlas. |
| `data_analytics/features/` | Matrices de features versionadas. |
| `data_analytics/modelos_icc/` | Referencias, modelos y scoring reproducidos con datos locales. |
| `ml/` | Piloto ICC de personas humanas y flujo IEF de Base C (`ief.py`, `baseline_ief.py`, `isolation_ief.py`). |
| `data_analytics/modelos_ief/` | Matrices, baseline, modelo, scores y protocolos versionados por consolidación. |
| `experimentos/icc/` | Extensiones autónomas, con sus fuentes y resultados. |
| `analisis/` | Notebooks explicativos de calidad y EDA. |
| `docs/` | Diseño, decisiones, planes y validaciones. |

## Entorno y ejecución

La integración del ICC fue comprobada con Python 3.12. Sus dependencias están
en `requirements_icc.txt`, que incluye las dependencias principales.

```bash
python -m pip install -r requirements_icc.txt
```

Reconstruir las tablas con fuentes guardadas, sin descargar datos:

```bash
python actualizar_bases.py
```

Actualizar únicamente las ofertas B y consolidar las tres bases:

```bash
python actualizar_bases.py --extract b
```

Actualizar las fuentes de las tres bases y reconstruir sus tablas:

```bash
python actualizar_bases.py --extract a b c
```

Los comandos de extracción consultan fuentes externas. Para revisar esta
entrega basta con los datos y resultados ya incluidos. Los experimentos
autónomos no se actualizan implícitamente al ejecutar el coordinador ABC.

Consultar [LEEME_ICC.md](LEEME_ICC.md) para ejecutar el piloto y las extensiones.
La suite vigente del piloto es:

```bash
python -m unittest docs.validar_features_icc_v3 docs.validar_evaluate_features docs.validar_icc_s1 docs.validar_icc_factor docs.validar_icc_pca2 -q
```

## Matriz de Base C

Matriz real, tratamiento, baseline y detector retrospectivo:

```bash
python ml/ief.py
python ml/baseline_ief.py
python ml/isolation_ief.py entrenar
python -m unittest docs.validar_modelo_ief docs.validar_ief -q
```

Para usar el bosque distribuido o reproducir los artefactos por hash, instalar
las versiones indicadas en [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md#entorno-de-referencia).
El diccionario, cobertura y comandos de reproducción están en
[Features IEF](docs/features_ief.md); el experimento completo, en
[Plan de Base C](docs/plan_ief.md). El [baseline IEF](docs/baseline_ief.md)
documenta prioridades mensuales y empates. El [modelo IEF](docs/modelo_ief.md)
explica el entrenamiento, aplicación sin fit, resultados y limitaciones.

## Documentación de referencia

- [Diseño de tablas](docs/diseno_tablas.md): grano, claves, unidades y consumidores.
- [Criterios económicos](docs/criterios_datos.md): preparación, S1 y controles.
- [Diccionario de features](docs/features_icc.md): variables del piloto.
- [Plan ML](docs/plan_ml.md): alcance y decisiones hasta el último cierre.
- [Validación de la integración](docs/validacion.md): pruebas y reproducción.

Conservar identificadores, ceros reportados y faltantes sin confundirlos. No
mezclar poblaciones ni monedas, no sumar subsectores solapados y no convertir
las claves de ofertas en identidades persistentes de productos. Las capturas
retrospectivas no certifican disponibilidad histórica contemporánea. Los
puntajes no son probabilidades de default ni recomendaciones personalizadas.
