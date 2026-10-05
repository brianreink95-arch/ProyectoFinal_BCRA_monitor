# Análisis de los datos

Estos son los cuatro notebooks finales. Son documentos explicativos; la extracción y
transformación operativa se ejecuta con los scripts Python de la raíz.

| Notebook | Qué responde |
|---|---|
| `01_calidad_base_a.ipynb` | ¿Las series monetarias y crediticias tienen cobertura, estructura y valores consistentes? |
| `02_calidad_base_b.ipynb` | ¿Los snapshots de ofertas están completos y sus campos son interpretables? |
| `03_calidad_base_c.ipynb` | ¿El panel de empresas conserva el universo y reconcilia deuda, entidades y meses? |
| `04_analisis_conjunto.ipynb` | ¿Qué muestran crédito, ofertas y deuda empresarial, y cuáles son los límites de comparación? |

Los tres primeros documentan calidad. El cuarto desarrolla los hallazgos conjuntos.
Los resultados guardados corresponden a los datos históricos analizados en septiembre de 2026.
Abrir un notebook muestra esos resultados sin necesidad de ejecutarlo.

Para recalcular, seleccionar el entorno instalado con `requirements.txt` y ejecutar todas las celdas,
desde esta carpeta o desde la raíz del proyecto. No se consultan APIs.
El análisis conjunto genera tablas y figuras nuevas en `analisis/resultados/` y conserva
explícitamente la corrida C histórica configurada; cambiar `RUN_C` si se quiere analizar otra.
No se modifican los archivos fuente. Los exports anteriores están en el ZIP histórico.

Los notebooks explicativos no consumen todavía los CSV relacionales; reutilizan las funciones sobre las fuentes históricas. El primer consumidor operativo ya es [ml/features.py](../ml/features.py), con la matriz ICC hipotecaria documentada en [features_icc.md](../docs/features_icc.md); no modifica ni reejecuta estos notebooks. La auditoría C quedó fijada a su corrida final de septiembre; el contrato y las pruebas relacionales verifican las corridas nuevas.
