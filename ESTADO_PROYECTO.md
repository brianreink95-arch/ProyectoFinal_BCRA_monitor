# Estado del Observatorio de Financiamiento y Endeudamiento

Actualización del 8 de noviembre de 2026. El ZIP parte de `proyecto(1).zip` e
incorpora el trabajo del 21 de octubre que quedó en el último `proyecto.zip`.
La corrida analítica de referencia es `20261006_231124_214604`, bajo contrato
relacional 2.0. Las fechas de captura siguen siendo las de esa corrida.

## Qué está implementado

| Área | Estado | Dónde seguir |
| --- | --- | --- |
| Integración ABC | Tres pipelines y 13 tablas relacionales. El coordinador puede reconstruir las tablas desde las capturas locales. | [README.md](README.md) y [diseño de tablas](docs/diseno_tablas.md) |
| Base A e ICC | 65 series, 41.687 observaciones y 117 meses de IPC. Hay siete ICC particulares experimentales, con 112 meses puntuados por segmento. El piloto hipotecario conserva S1 después de contrastar PCA y análisis factorial. | [LEEME_ICC.md](LEEME_ICC.md) y `experimentos/icc/` |
| Base B | 46.586 ofertas de 13 capturas completas en cuatro familias. El indicador de atractivo de productos (IAP) queda para cuando haya suficiente historia de capturas diarias. | `base_b.py` y `analisis/02_calidad_base_b.ipynb` |
| Base C e IEF | Panel intencional de 100 empresas y 2.400 filas empresa-mes. Matriz 0.2 con seis predictores, baseline mensual 0.1 y detector Isolation Forest 0.1. Hay 2.047 filas puntuadas. El ajuste usa las 875 elegibles de entrenamiento. | [Modelo IEF](docs/modelo_ief.md) y `ml/ief.py`, `ml/baseline_ief.py`, `ml/isolation_ief.py` |

El top 5 mensual de Base C coincide con el baseline en promedio en un 80,07 %
durante la validación y un 86,67 % en la evaluación retrospectiva. Son
medidas de concordancia entre rankings descriptivos. Quedan como mejoras el
contraste con deterioros del mes siguiente, la evaluación por grupos reservados,
la revisión de casos y un notebook propio del IEF. También quedan pendientes
el ICC global, el IAP y la aplicación web con capturas programadas.

## Qué cambió respecto de tu ZIP

La comparación encontró 19 archivos incorporados y 6 actualizados en la última
versión de octubre. Los 585 archivos restantes coincidían byte por byte. Los
19 nuevos son 3 módulos Python, 6 archivos de documentación y pruebas, y
10 artefactos del IEF. La actualización de hoy agrega esta guía, enlaza el estado
actual desde el README y actualiza las instrucciones para Copilot en VS Code.
El inventario incluye esos cambios. Los pipelines, fórmulas del ICC y datos
históricos coinciden con los de tu ZIP.

## Sincronizar tu clon

Extraé el ZIP fuera del clon. Desde la raíz de tu repositorio, revisá
`git status --short` y `git remote -v`. Si hay cambios locales, guardalos o
integralos antes de copiar. Si el árbol está limpio, podés usar
`git switch -c sync/base-c-ief` para revisar la actualización en una rama.

Si tu clon coincide con el ZIP que adjuntaste, copiá estos archivos de la
carpeta `proyecto` extraída a las rutas equivalentes del clon. Si el clon tiene
ediciones posteriores en alguna de esas rutas, compará ambas versiones antes
de reemplazarla.

| Grupo | Rutas que hay que copiar |
| --- | --- |
| Código IEF | `ml/ief.py`, `ml/baseline_ief.py`, `ml/isolation_ief.py` |
| Pruebas IEF | `docs/validar_ief.py`, `docs/validar_modelo_ief.py` |
| Documentación IEF | `docs/plan_ief.md`, `docs/features_ief.md`, `docs/baseline_ief.md`, `docs/modelo_ief.md` |
| Documentación general | `README.md`, `LEEME_ICC.md`, `ESTADO_PROYECTO.md`, `.github/copilot-instructions.md`, `docs/plan_ml.md`, `docs/validacion.md`, `docs/inventario_proyecto.json`, `docs/verificacion_proyecto.json` |
| Artefactos locales | `data_analytics/modelos_ief/20261006_231124_214604/` completa |

El ZIP completo también sirve para restaurar los datos locales si el clon se
descargó de cero. Para reproducir los resultados, conservá `data_a/`,
`data_b/`, `data_c/`, `data_analytics/`, `config/empresas_base_c.xlsx` y los
insumos de `experimentos/icc/` en sus rutas originales. El `.gitignore` excluye
capturas, datasets y modelos. Git solo subirá los archivos versionados o los
que agregues explícitamente.

Después de copiar y revisar los diffs, desde el clon:

```powershell
git add -- README.md LEEME_ICC.md ESTADO_PROYECTO.md .github/copilot-instructions.md ml/ief.py ml/baseline_ief.py ml/isolation_ief.py
git add -- docs/validar_ief.py docs/validar_modelo_ief.py docs/plan_ief.md docs/features_ief.md docs/baseline_ief.md docs/modelo_ief.md docs/plan_ml.md docs/validacion.md docs/inventario_proyecto.json docs/verificacion_proyecto.json
git diff --cached --stat
git diff --cached --check
git commit -m "Sincronizar el modelado empresarial de Base C"
git push -u origin sync/base-c-ief
```

El comando de push asume que el remoto correcto se llama `origin`. Abrí el
clon en VS Code y usá este documento como contexto inicial del asistente.

## Entorno de referencia

La reproducción se verificó con Python 3.12.14 en Linux. En Windows podés usar
VS Code con WSL para repetirla en Linux. Extraé el ZIP directamente en WSL si
querés preservar los bytes de las fuentes y artefactos de referencia. Seleccioná
en VS Code el intérprete de un entorno Python 3.12 y ejecutá:

```bash
python -m pip install -r requirements_icc.txt "scikit-learn==1.8.0" "joblib==1.5.3"
python -m unittest docs.validar_ief docs.validar_modelo_ief -q
python ml/isolation_ief.py entrenar --output-dir ../reproduccion-ief/bosque
python ml/isolation_ief.py puntuar --model-dir ../reproduccion-ief/bosque --output-dir ../reproduccion-ief/score
```

`requirements_icc.txt` ya fija pandas 2.2.3, NumPy 2.3.5 y SciPy 1.17.0.
El flujo de arriba parte de la
matriz y el baseline que vienen en el ZIP. Para regenerar esas etapas, ver
[README.md](README.md#matriz-de-base-c). El entrenamiento de referencia queda
asociado a la corrida de octubre. Para reconstruir ABC por separado, usá
`python actualizar_bases.py --out-root ../reproduccion-abc`.

## Verificación de esta actualización

- 263 pruebas aprobadas, incluidas 56 de Base C e IEF. Se ejecutaron las
  celdas de los cuatro notebooks sin nuevas consultas al BCRA.
- Se verificaron los hashes de las 342 fuentes y de las 13 tablas guardadas.
  Las 13 tablas reconstruidas localmente coinciden con las de referencia al
  normalizar los saltos de línea de CSV.
- La matriz tratada, el baseline, el bosque y el CSV de scores se reprodujeron
  byte por byte en el entorno de referencia.
