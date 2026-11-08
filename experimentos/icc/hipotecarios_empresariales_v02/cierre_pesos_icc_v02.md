# Cierre de pesos del ICC hipotecario empresarial — versión 0.2
Decisión y aplicación: 15 de octubre de 2026.

## Resultado aplicado
| Segmento | Peso costo | Peso momentum | Decisión | ICC junio 2026 |
|---|---:|---:|---|---:|
| Hipotecarios ML PyMEs 935 |60% |40% |Cambiar respecto de 0.1 |19,9270 |
| Hipotecarios ML No PyMEs 936 |80% |20% |Conservar ponderación 0.1 |19,4237 |

**Estado: cerrado experimental para uso descriptivo interno.** Los pesos están decididos y aplicados. No quedan como candidatos pendientes. No se afirma optimalidad estadística ni validación operativa.

Fórmulas: 935=100V(0,60C+0,40M); 936=100V(0,80C+0,20M).
Se mantienen V/C/M y las referencias de los 60 meses de train de cada segmento. C sigue siendo proxy de tasa nominal fija/repactable. No se modifican PH927, la reserva ni el global. La versión 0.1 se preserva. La integración web no fue realizada.

## Plan ejecutado y criterio de elección
Se completaron los seis pasos: compensaciones, escenarios, contraste ECC, robustez, decisión y aplicación. Se usa la salida prevista para evidencia sin ganador único: una **convención económica explícita apoyada por diagnósticos**, sin afirmar un óptimo.

El criterio es equilibrar la tasa nominal con el volumen y la dinámica reales. Se reduce la prioridad del costo donde la evidencia descriptiva acompaña; no se impone el 60/40 a un segundo segmento cuya evaluación no muestra la misma ventaja. Son dos reglas discretas justificadas, sin ajuste continuo por episodio.

## Fuente y cobertura externa
Se descargó el histórico oficial ECC-Empresas.xlsx, hasta 2026-II. Se extrajeron las hojas 1 (estándares observados), 4 (spread, plazo y garantías observados) y 6 (demanda observada), usando IDs ponderados por entidad y respuesta. Se excluyeron las expectativas.

El original, la tabla normalizada y los localizadores de hoja/fila/columna se incluyen en el paquete. Se contrastaron **37 trimestres continuos, 2017-II–2026-II**, con cambios del ICC entre cierres. No se comprimen faltantes. Cada indicador conserva 112 meses puntuados, marzo 2017–junio 2026.

935 se compara con ECC PyMEs. 936 se compara con Grandes Empresas como proxy parcial: no es idéntica población. La ECC abarca crédito empresarial amplio, no sólo hipotecarios.

Fuentes:
- [ECC e histórico oficial](https://www.bcra.gob.ar/encuesta-condiciones-crediticias-ecc/)
- [ECC Empresas XLSX](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/ECC/ECC-Empresas.xlsx)
- [Características y formulario](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/ECC_Caracteristicas_y_formulario.pdf)

Los IDs miden cambios trimestrales: no se equiparan sus niveles −100/+100 al nivel 0–100 del ICC. Estándares, términos y demanda son conceptos distintos.

## Contraste que sustenta la decisión
Spearman contemporáneo entre ΔICC trimestral e ID de cada dimensión, sobre 37 trimestres. Son descriptores ex post, sin prueba de significación ni inferencia causal.

| Segmento | Pesos C/M | Demanda | Estándares | Spread | Plazo | Garantías |
|---|---|---:|---:|---:|---:|---:|
| PyMEs |50/50 |0,499 |0,379 |0,468 |0,351 |0,192 |
| PyMEs |**60/40** |**0,495** |**0,368** |**0,524** |**0,346** |**0,191** |
| PyMEs |70/30 |0,442 |0,311 |0,560 |0,317 |0,156 |
| PyMEs |80/20 |0,396 |0,262 |0,611 |0,286 |0,139 |
| No PyMEs |50/50 |0,175 |0,070 |0,326 |0,011 |0,011 |
| No PyMEs |60/40 |0,190 |0,080 |0,350 |0,012 |0,010 |
| No PyMEs |70/30 |0,197 |0,099 |0,394 |0,024 |0,044 |
| No PyMEs |**80/20** |**0,217** |**0,127** |**0,427** |**0,049** |**0,077** |

**PyMEs: 60/40.** Conserva demanda y estándares próximos a 50/50, con más correspondencia con spreads. Frente a 80/20 aumenta la relación con demanda, estándares y plazo, a cambio de menor relación con spread. Se mantiene prioridad moderada al costo y se amplía la dinámica real. Ninguna alternativa domina todos los criterios; no se inventa un promedio de métricas para declarar vencedor.

**No PyMEs: 80/20.** Pasar a 60/40 reduce las correlaciones de las cinco dimensiones en la comparación completa, con igual número de coincidencias direccionales bajo el umbral principal. No hay ventaja consistente para cambiarlo. Las relaciones con estándares/plazo/garantías son débiles: conservar 80/20 no prueba su superioridad poblacional ni valida una medida integral de condiciones.

La propuesta inicial de aplicar 60/40 a ambos se limita a 935 al incorporar nueva evidencia. Tampoco se sostiene que distintos pesos hagan comparables los niveles.

## Robustez completada
Se conservan los 11 pesos y 8 escenarios previos; la decisión se concentra en 50/50, 60/40, 70/30 y 80/20.

Se revisaron neutralidad ECC |ID|≤5, bandas de ΔICC ±0,5/±1/±2 puntos, exclusión de cada episodio y año, y desplazamiento conjunto de cierres −1/0/+1 mes conservando duración. Las bandas del ICC son sensibilidades, no umbrales operativos.

Al excluir años o episodios, la ventaja de 60/40 frente a 80/20 en PyMEs se mantiene para demanda (diferencia de rho +0,058 a +0,131), estándares (+0,084 a +0,149) y plazo (+0,040 a +0,081). La pérdida frente a spread también permanece (−0,106 a −0,038). Se observa un compromiso estable entre dimensiones, no dominancia general.

Las coincidencias de signo dependen de la banda. Con ±1 punto, PyMEs pasa de 18/32 a 20/32 coincidencias con demanda y de 11/21 a 13/21 con estándares. No equivalen a accuracy de un target validado. En No PyMEs ambos pesos tienen 14/31 y 9/22, respectivamente. No se ocultan los resultados de las otras bandas.

Los giros de 2018, 2023 y 2024-II conservan su signo con 60/40 al desplazar los cortes. La intensidad del rebote de No PyMEs en 2021 varía mucho según el corte. El episodio 2024-I cambia de signo al extenderse hacia abril, cuando comienza el giro. En 2026-II el desplazamiento +1 mes queda sin resultado porque entra a reserva.

## Divergencias conservadas
- **2020-II, PyMEs:** ICC60/40 +7,76 puntos y estándares ECC −7,13; mejoran spread (+58,90) y demanda (+40,15). Coinciden unas dimensiones y diverge otra.
- **2024-III, No PyMEs:** ICC80/20 −6,74 puntos, estándares +15,58 y demanda +21,17; spread casi neutral (−4,35). Es una divergencia sin explicación causal resuelta.
- **2026-II:** ambos índices aumentan mientras cada grupo ECC registra menor demanda y estándares restrictivos, con spreads más flexibles. La explicación debe identificar qué mejora y qué no mide el ICC.

No se borran períodos discordantes ni se cambian pesos para corregirlos uno por uno. Plazos, garantías y estándares no son inputs directos del índice.

## Aplicación y validación
Se publicaron icc_935_v02.csv, icc_936_v02.csv y sus modelos JSON. 935 se recalcula; 936 reproduce los 112 valores de 0.1 con nueva metadata. Los campos distinguen adopción descriptiva de habilitación operativa e integración web.

Ocho pruebas específicas verifican ECC observada, 37 trimestres continuos, pesos aplicados, referencias sin refit, conservación numérica de 936, cambio efectivo de 935, reserva/nulos y reconciliación de aportes/rango. Se verifica ejecución repetida idéntica y hashes.

No se reentrenan PCA/FA para intentar admitirlos con otro comparador. Sus rechazos históricos se conservan como evidencia de 0.1; no se afirma reevaluación bajo 60/40.

Desde esta carpeta ejecutar:
    python -m pip install -r requirements.txt
    python cierre_icc.py --apply
    python -m unittest validar_cierre -v

El paquete consume los snapshots incluidos y la decisión explícita; no descarga fuentes ni modifica el proyecto principal.

## Alcance del cierre
Quedan cerrados los pesos y resultados de 0.2 para exploración descriptiva interna. La evidencia histórica ya fue examinada, no es test intacto. La ponderación no resuelve la proxy nominal, la equivalencia parcial de población/modalidad ni las discrepancias previas de fuentes.

Validación prospectiva, alertas operativas, integración técnica y global mantienen sus etapas separadas. El próximo segmento pendiente sigue siendo 929. Una recalibración posterior debe tener nueva versión.

