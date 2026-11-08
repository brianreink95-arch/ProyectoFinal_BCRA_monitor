# Evaluación hipotecarios empresariales 0.1

Esta carpeta forma parte del proyecto depurado. Usa código o insumos compartidos
con las otras carpetas del proyecto; ejecutar dentro de la carpeta `proyecto`
completa. El punto de entrada es `../../../LEEME_ICC.md`.

Evaluación de PyMEs y No PyMEs con fuentes congeladas, código compartido, CSV y diagnósticos.
**Descomprimir en una carpeta separada. No copiar este ml/ sobre el ml/ de tu proyecto.**
Ejecutar desde esta carpeta:
```bash
python -m pip install -r ../../../requirements_icc.txt
python evaluar_hipotecarios.py
python -m unittest validar_empresariales -v
```
No requiere red. Reutiliza S1/PCA/FA/PCA2 del piloto con adaptador empresarial explícito.
Fuente nominal de tasa fija/repactable; no UVA ni CFT. Score experimental, no ICC aprobado.
Resultados en resultados/935 y resultados/936. Julio2026 en adelante no se puntúa.
El informe docs/evaluacion_hipotecarios_empresariales.md registra método, pesos y limitaciones.
Las fuentes originales/API se conservan para comparar revisiones sin mezclar vintages.
Para integrar al proyecto principal, formalizar primero contrato de población/modalidad y añadir módulo específico; los comandos originales PH siguen siendo independientes.

