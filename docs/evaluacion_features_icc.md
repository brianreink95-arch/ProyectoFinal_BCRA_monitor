# Evaluación descriptiva de las variables del ICC

El evaluador vigente es `ml/evaluate_features.py`, versión 1.1. Lee la matriz
3.0 y reconstruye sus fuentes locales antes de comparar cobertura, identidades,
correlaciones y cambios de distribución. No selecciona variables automáticamente.
La fórmula S1 ya fue adoptada; este diagnóstico de variables no la sustituye.

Ejecutar desde la raíz:

```bash
python ml/evaluate_features.py
python -m unittest docs.validar_evaluate_features -q
```

La salida vigente está en
`data_analytics/evaluaciones_features/20261006_231124_214604/v1.1/`:
`informe_icc.html` para lectura y `diagnostico_icc.json` para resultados estructurados.

El calendario train tiene 67 meses y el core de volumen real, crecimiento
trimestral y TNA UVA comparte 60. Validación tiene 22 meses y retrospectiva 30.
Usar todas las candidatas exige 51 meses de train y no cumple el mínimo de 60.
El costo es una proxy parcial y el saldo no mide acceso individual. Ver
`features_icc.md`, `criterios_datos.md` y `plan_ml.md` para definiciones y decisiones.
