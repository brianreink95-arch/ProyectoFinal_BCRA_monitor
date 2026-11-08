# Baseline IEF 0.1 — prioridad mensual de revisión

Implementado sobre la matriz tratada 0.2 de la consolidación
`20261006_231124_214604`. Consumidor: referencia interpretable para contrastar
el detector de anomalías del plan IEF. Isolation Forest ya está entrenado y
comparado descriptivamente: ver `modelo_ief.md`.

## Regla y universo

Dentro de cada mes, ordenar de mayor a menor por esta tupla, en este orden:

1. `situacion_max_activa`;
2. `pct_deuda_situacion_2_mas`;
3. `baseline_aumento_3m_pp = max(pct_deuda_situacion_2_mas_delta_3m_pp, 0)`.

Es una prioridad lexicográfica: el primer criterio prevalece sobre los otros
dos. No se suman los componentes ni se ajustan pesos o umbrales. El tercer
criterio distingue aumentos positivos; una reducción y un cambio nulo empatan
si coinciden los dos criterios anteriores. El delta original se conserva.

Se usa el mismo universo elegible que el futuro bosque: 875 filas de train,
587 de validación y 585 de evaluación, 2.047 en total. Se preservan las 2.400
filas, sus variables y motivos originales; las 353 no elegibles quedan con
posiciones y participaciones nulas. No se las clasifica como normales.
Los tres primeros meses carecen de ranking por falta de historia trimestral.

El baseline se calcula con información de cada fila y sus pares del mismo mes.
No hay fit, calibración, target futuro ni ajuste de referencias. No se crea una
escala 0–100. Una posición menor significa mayor prioridad según esta regla,
no una probabilidad ni una medida de estrés validada. Los bloques temporales
se conservan para la comparación posterior.

## Posiciones, empates y top-k

`baseline_posicion_desde` es uno más que la cantidad de empresas con tupla
estrictamente superior. `baseline_posicion_hasta` agrega la cantidad empatada
menos uno. `baseline_n_empatadas` cuenta a todas las empresas del grupo, incluida
la fila. Una primera prioridad sin empate tiene intervalo `[1, 1]`.

Los empates exigen igualdad exacta de los tres componentes, con la precisión
guardada. No se redondean predictores ni se usa CUIT, tamaño o razón social para
desempatar. El orden del CSV es solo de presentación por CUIT y mes.

Para top 5 y top 10, cada empresa recibe participación:

```text
peso_top_k = clip((k - posicion_desde + 1) / n_empatadas, 0, 1)
```

Si tres empresas ocupan las posiciones 4 a 6, cada una recibe peso `2/3` en el
top 5. Se muestran las tres, sin elegir dos por orden alfabético. La suma de
participaciones es `min(k, numero_elegibles_del_mes)`. Este peso representa
capacidad de revisión compartida; no es probabilidad de deterioro ni un score.
Los meses sin elegibles suman cero; sus filas mantienen pesos nulos.

En los datos actuales, el top 5 cruza un empate en 7 de los 21 meses con
ranking. El top 10 lo hace en 20. En diciembre de 2024, por ejemplo, hay cuatro
empresas por encima de un empate de 93: cada una de esas 93 recibe `1/93` en
el top 5. Este resultado muestra la escasa discriminación del baseline entre
empresas sin señales informadas, y debe conservarse en la comparación.

## Resultado ilustrativo: julio de 2026

Hay 99 empresas elegibles y ninguna igualada en el borde del top 5:

| Posición | Empresa | Situación máxima activa | Deuda en situación ≥2 | Aumento trimestral positivo, pp |
| ---: | --- | ---: | ---: | ---: |
| 1 | MANISUR S.A. | 5 | 100% | 0 |
| 2 | Vicentin S.A.I.C. / Nueva Vicentin Argentina | 5 | 99,88097% | 99,88097 |
| 3 | MOLINO CAÑUELAS S.A.C.I.F.I.A. | 5 | 94,17041% | 0 |
| 4 | Cargill S.A.C.I. | 5 | 0,00006264% | 0,00006264 |
| 5 | Granja Tres Arroyos S.A.C.A.F.e.I. | 4 | 78,06125% | 48,22088 |

Las cifras de esta tabla están redondeadas solo para lectura. Cargill aparece
antes que Granja Tres Arroyos porque el máximo de situación prevalece, aunque
su proporción de deuda en situación ≥2 sea mucho menor. Es una consecuencia
explícita y una limitación de la regla acordada; no demuestra mayor estrés
económico integral. El baseline se conserva para contrastarlo con el bosque,
sin modificar la regla después de ver qué empresas quedan arriba.

La coincidencia con situaciones ya informadas mide coherencia descriptiva.
No constituye evidencia de anticipación ni de utilidad incremental. El panel
es sectorial y retrospectivo; no acredita disponibilidad pública contemporánea.

## Ejecución y archivos esenciales

Desde la raíz del proyecto:

```bash
python ml/baseline_ief.py
python -m unittest docs.validar_ief -q
```

El módulo usa `ml/ief.py` sin modificarlo y verifica el bundle 0.2 congelado:
hashes de CSV, contrato, tablas, código y dependencias; protocolo, orden de
predictores y reconstrucción idéntica con referencias guardadas, sin refit.
El módulo separado conserva la reproducibilidad y la procedencia del tratamiento.

```text
data_analytics/modelos_ief/20261006_231124_214604/baseline_v0.1/
  baseline_ief.csv
  protocolo_baseline.json
```

El CSV contiene las filas originales y seis columnas nuevas: aumento positivo,
intervalo de posiciones, tamaño del empate y participaciones top 5/top 10.
El JSON registra regla, interpretación, límites, cobertura, resumen de los 24
meses, versiones y hashes. Las sumas del resumen se redondean a 12 decimales
solo para eliminar ruido de coma flotante; los pesos del CSV no se redondean.

Un destino existente debe ser idéntico. Para una reproducción independiente:

```bash
python ml/baseline_ief.py --output-dir reproduccion_ief/baseline
```

`--features-dir` permite indicar un bundle 0.2 congelado explícito y validado.
Los errores no publican carpetas parciales ni sobrescriben bundles diferentes.
No se consultan fuentes en línea ni se agregan dependencias.

Las pruebas cubren orden lexicográfico, prioridad de una situación alta sobre
una proporción mayor, tercer criterio positivo, empates totales y en el borde,
universos menores que k, masa top-k, filas sin ranking, invariancia ante orden
de entrada/CUIT y meses posteriores, integridad, aplicación sin refit y publicación.
El desempeño frente a deterioros futuros y el contraste con el bosque se
implementarán en la etapa de evaluación, sin incorporar etiquetas al baseline.
