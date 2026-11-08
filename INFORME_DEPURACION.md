# Depuración del proyecto completo

Se revisaron los archivos del proyecto original y las entregas recuperadas del
ICC. La selección se basó en lecturas y escrituras de los scripts, imports,
rutas de notebooks, punteros de versión, hashes, consumidores y pruebas.
El resultado es un ZIP completo para abrir como proyecto en VS Code.

Se retiraron 180 archivos lógicos redundantes, sustituidos o sin consumidor
necesario en la distribución, equivalentes a 104,55 MB sin comprimir. También
se excluyeron cachés, temporales y metadatos de ejecución local. El detalle está
en `docs/archivos_retirados.csv`.

## Qué se retiró

- Tres consolidaciones ABC anteriores, conservando la corrida vigente y sus
  fuentes completas. Dos repetían las 13 tablas vigentes; la primera correspondía a la preparación
  anterior al ajuste real.
- Matrices de features anteriores y el baseline nominal sustituido por S1.
- Las copias `resultados_s1`, `resultados_factor` y `resultados_pca2`, porque
  existe una reproducción canónica completa en `data_analytics/modelos_icc/`.
- Copias de módulos ML y utilidades dentro del experimento empresarial. Ahora
  usa las implementaciones centrales del proyecto.
- Snapshots empresariales idénticos a los compartidos con las otras series y
  CSV de entrada duplicados en la comparación de pesos.
- Las 42 trayectorias por combinación serie/peso de otras series. Se conservan
  índices seleccionados, parciales, referencias, métricas, contrastes y decisiones;
  las trayectorias completas se regeneran ejecutando el experimento.
- Los 28 JSON repetidos de controles por serie/peso. Su contenido se conserva
  en una sola tabla `controles_escenarios.csv`.
- Inventarios vencidos, guías de copiar parches, deliberaciones de sesiones y
  suites sustituidas. El plan ML se reescribió con el estado vigente y los
  criterios conservan las decisiones técnicas necesarias.

## Qué se conserva

La ingesta y transformación A/B/C, los contratos, catálogo y maestro de empresas,
una consolidación completa vigente, las features actuales, S1, entrenamiento,
scoring, los siete ICC particulares, sus referencias y las pruebas vigentes.

Se conservan los modelos rechazados y sus diagnósticos porque sustentan la
decisión de usar S1. El experimento empresarial 0.1 sigue siendo necesario para
reproducir esos rechazos y obtener las referencias de la comparación de pesos;
el cierre 0.2 es la salida vigente.

Las capturas históricas B y C no son duplicados eliminables por compartir
fecha o valores: sostienen la historia, los notebooks y los hashes de
procedencia. Se comprobaron las 342 fuentes de la consolidación vigente.

## Cómo usar esta entrega

Extraer la carpeta `proyecto` en un directorio nuevo y abrirla en VS Code.
Leer `README.md` y `LEEME_ICC.md`. Los resultados están incluidos.

```powershell
python -m pip install -r requirements_icc.txt
python ml/baseline.py --check-only
```

Instalar en un entorno compatible con Python 3.12, que es la versión verificada.
Los experimentos comparten módulos e insumos y se ejecutan dentro del proyecto
completo, respetando las carpetas incluidas.

Las salidas intermedias retiradas se pueden generar en una carpeta de trabajo
nueva siguiendo los comandos de cada módulo. El coordinador ABC y los scripts
de extracción siguen disponibles para incorporar datos posteriores.

## Comprobaciones finales

Se aprobaron 207 pruebas de código y datos; se ejecutaron las celdas de los
cuatro notebooks; se cotejaron los siete índices sin diferencias en sus
puntajes; se verificaron los hashes de fuentes y las rutas de los consumidores.
El registro técnico está en `docs/validacion.md` y
`docs/verificacion_proyecto.json`.

El ICC global, IAP, IEF, la aplicación web y las alertas operativas permanecen
pendientes. La depuración no cambia el alcance metodológico del proyecto.
