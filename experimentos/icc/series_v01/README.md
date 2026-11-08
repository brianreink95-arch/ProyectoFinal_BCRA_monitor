# ICC — evaluación de series pendientes 0.1

Auditoría y exploración de 17 stocks pendientes, incorporación de cuatro stocks
de consumo y evaluación reproducible de candidatos bajo un protocolo explícito.

El informe principal es [informe_cierre_series_icc.md](informe_cierre_series_icc.md).
El análisis previo y sus fuentes están en [exploracion_inicial.md](exploracion_inicial.md).

## Resultado de la versión

- Cuatro nuevos ICC experimentales: prendarios PH ML 50/50; prendarios PyMEs ME
  50/50; personales ML privado 60/40; tarjetas ME privado 60/40.
- Nueve indicadores parciales IVD, siete series de contexto y una
  exclusión/diferimiento. El detalle completo está en resultados/registro_decisiones.csv.
- Los tres ICC anteriores no se recalculan ni se sustituyen.
- Global bloqueado: ver resultados/decision_global.json. No hay integración web
  ni habilitación operativa. Las proxies y los contrastes externos débiles se
  mantienen explícitos en el informe.

## Reproducir sin red

Entorno probado: Python 3.12; versiones exactas en entorno_verificado.json.
Instalar requirements.txt en un entorno de trabajo y ejecutar desde este directorio:

    python ejecutar.py --fase todo --output resultados_repeticion
    python validar.py --output resultados_repeticion

La opción eda ejecuta solo auditoría/exploración; todo incluye los candidatos y
decisiones. Ejecutar en un directorio nuevo para conservar la entrega de referencia.
No modificar fuentes o protocolo para intentar reproducir los resultados actuales.
Un experimento con cambios requiere otra versión y otro destino.

generar_informe.py reconstruye el informe desde resultados/ y verificacion.json.
Las figuras se producen con matplotlib y quedan en graficos/ en la corrida
incluida, o en el subdirectorio graficos del destino alternativo.

## Datos y alcance

fuentes/ conserva los snapshots originales y el IPC. API/XLS pueden representar
revisiones diferentes; no se empalman por mes. Los archivos heredados son el
stock por titular capturado el 5/10, las tasas capturadas el 8/10 Buenos Aires
(9/10 UTC), el IPC y la consolidación del 5/10. Las nuevas descargas finserprom,
montos operados, A3500, ECC Familias y metodologías se capturaron el 15/10/2026.
ECC Empresas proviene del cierre empresarial anterior. No son vintages históricos.
Los hashes de cada archivo están en resultados/procedencia_*.json.

ML se deflacta por IPC nacional; ME se trabaja en USD equivalentes nominales.
En ME por titular se revierte la conversión con A3500 de cierre, conservando su
fecha y sin usar TCNPM. No se deflactan dólares con IPC argentino.

finserprom son promedios de saldos diarios del privado no financiero; perser_priv
son saldos de cierre por titular. Las claves locales finserprom_* no son IDs BCRA.
Los montos de preser_mon sirven para interpretar tasas y flags: en tarjetas
representan la base de saldos de liquidaciones, no originaciones como personales.

## Archivos analíticos

- catalogo_auditado.csv: unidades y correspondencias de stock/tasa.
- calidad_elegibilidad.csv: cobertura core; el registro agrega cobertura propia IVD.
- features/: series originales normalizadas, medidas de volumen, tasas y flags.
- composicion_moneda_y_residuales.csv, prendarios_destinos.csv: aperturas auditadas.
- candidatos/: trayectorias regenerables al ejecutar el experimento; no se distribuyen 42 CSV repetidos.
- controles_escenarios.csv: los 28 controles económicos consolidados por serie/peso.
- indices/: solamente los cuatro candidatos que pasan el protocolo 0.1.
- parciales/: IVD sin costo, distinto del ICC.
- sensibilidades.csv: nueve variantes por peso, train/validación.
- contraste_ecc.csv, robustez_ecc.csv y pares_ecc_icc.csv: evidencia externa observada.
- epocas_stock_tasa.csv y epocas_indices.csv: comparación retrospectiva por época.

Las subcarpetas citadas pertenecen a resultados/. Los CSV conservan faltantes;
no se interpretan como cero. Cada índice tiene referencias propias y sus niveles
no son directamente comparables. Los cuatro nuevos cierres son descriptivos,
con pesos de convención bajo controles de estabilidad, no óptimos históricos.
