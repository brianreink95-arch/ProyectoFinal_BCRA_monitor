# Exploración inicial y decisión de diseño

15 de octubre de 2026. Documento fijado después de la EDA y antes de calcular los candidatos ICC de esta entrega. Los datos históricos ya se inspeccionaron: el ejercicio es retrospectivo y exploratorio.

## Fuentes y medida económica

Se auditaron los 17 stocks pendientes, se preservaron los tres cierres anteriores y se incorporaron cuatro stocks por producto (personales/tarjetas, ML/ME) desde finserprom.xls. Estos últimos describen al sector privado no financiero y son promedios mensuales de saldos diarios; no son saldos PH de cierre. Las claves finserprom_* son identificadores locales y no nuevos códigos de la API BCRA.

perser_priv.xls publica miles de ARS: dividir por 1.000 da millones de ARS. La API comparada publica magnitudes redondeadas en millones aunque declara miles. Se conserva la tabla de diferencias y se utiliza íntegro el snapshot XLS en este experimento, sin empalmar meses ni modificar las bases existentes.

La metodología oficial del Boletín, sección préstamos/depósitos privados por titular, establece valuación de cierre con referencia BCRA desde marzo de 2002. SISCEN-0011, pp. 74–75, requiere informar ME en dólares equivalentes. Para la etapa evaluada se reconstruye Q = saldo ME ARS / A3500 de cierre, usando la última observación publicada dentro de cada mes y conservando su fecha. Q es nominal en dólares equivalentes: no es poder de compra argentino, no se deflacta por IPC ARS y puede conservar efectos de otras paridades contra USD. finserprom ofrece directamente millones de USD equivalentes para ME.

## Hallazgos por familia

**Hipotecarios restantes.** 929 tiene 32 ceros en el XLS entre diciembre de 2016 y junio de 2026, frente a 41 publicados por API. La precisión recuperada no resuelve la falta de tasa de prestadoras. 940 tiene saldo cero en todos esos 115 meses, a la precisión original. Los otros hipotecarios ME tienen volumen reconstruible, pero las tasas contienen ceros ambiguos junto con montos cero. La cobertura útil se evalúa sin interpretarlos como financiamiento gratuito.

**Prendarios.** La garantía no determina un único destino: automotores, maquinaria y otros tienen participaciones diferentes por población y moneda. En junio de 2026 automotores representan 75,99% del saldo PH ML y 19,64% del PH ME; maquinaria representa 1,06% y 45,82%, respectivamente. La apertura PJ es agregada y no demuestra la composición específica de PyMEs/No PyMEs. Entre diciembre de 2017 y diciembre de 2019 los saldos reales ML de PH, PyMEs y No PyMEs cayeron 59,6%, 63,5% y 56,4%; Q de PyMEs ME aumentó 91,8%. No corresponde imponer la misma historia a todas las monedas.

La tasa fija/repactable por titular es una proxy parcial frente al saldo vigente de modalidades mixtas. Existe una apertura PH; 1218 es del conjunto privado, por lo que se conserva como contraste y no se aplica indiscriminadamente a PH o empresas. 962 carece de tasa específica de prestadoras. 973 es esparsa, con 89 ceros publicados en el período reciente.

**Personales.** El stock específico ML permite una lectura propia: cae 49,1% real entre diciembre de 2017 y diciembre de 2019 y 52,3% entre diciembre de 2021 y diciembre de 2023. Su recuperación posterior debe distinguirse de nivel alto de crédito y de costo real bajo. Se empleará la tasa mensual ponderada del mismo universo privado, no la media simple diaria de 14; esta última queda como contraste. El stock puede mezclar indexación y finalidades y el saldo no demuestra acceso individual ni bienestar. La línea ME es demasiado esparsa y sin tasa útil suficiente.

**Tarjetas.** El stock incluye financiación y modalidades que no coinciden con el costo de saldos a tasa distinta de cero. Se mantendrá visible esta brecha. La tasa 1215 tiene un hueco oficial mayo de 2020–julio de 2022 por los créditos a tasa cero. La alternativa 1220 y su columna equivalente en el XLS no rellenan ese hueco: representan otro concepto y se evaluarán como proxy propia. Los montos ponderadores de tarjetas corresponden a saldos de liquidaciones, no a desembolsos nuevos comparables a personales. ME se mide en USD equivalentes nominales; un saldo mayor puede estar asociado a consumos externos y cambios de composición, y no prueba expansión de oferta.

**Totales.** Se produjeron participaciones ML/ME y residuales total menos partes. Los residuales por titular no son universalmente de redondeo; se conservan. En junio de 2026 el saldo ME representa 5,23% del total PH, 30,90% PyME y 54,21% No PyME según el cuadro de cierre. Deflactar el total mixto solo produce exposición real en pesos. No se usará como volumen puro ni se sumará como exposición adicional a hipotecarios/prendarios/personales/tarjetas.

## Calidad, relaciones y rupturas

Se guardaron niveles, variaciones a 1/3/12 meses, cambios absolutos, aceleración, volatilidad, correlaciones descriptivas y rezagos 0/1/3, principales saltos, composición y cobertura. No se imputaron valores ni se comprimió el calendario. Ceros en el denominador impiden calcular tasas de crecimiento. Los saltos son candidatos a revisión, no rupturas causales identificadas automáticamente.

Una tasa positiva con monto publicado cero se conserva, con flag: puede reflejar redondeo o discrepancia entre capturas. Una tasa cero sin monto positivo se considera no interpretable. No se concluye ausencia absoluta de operaciones ni se inventa una tasa a partir de montos. Las cabeceras españolas de algunas hojas repiten un título genérico; la asignación se basa en nombre de hoja, cabecera inglesa específica y estructura completa, preservando el defecto de publicación.

## Decisión antes de los escenarios

Para los segmentos con volumen/costo/dinámica medibles se evaluará la forma S1 como descriptor interno, sin adjudicarle acceso ni costo real. ML usa saldo a precios de diciembre de 2016; ME usa saldo nominal en USD equivalentes y conserva un alcance separado. El costo es relativo a la historia nominal del segmento. No se considerarán equivalentes los niveles de estos índices ni se agregarán al global en esta entrega.

La forma V × combinación(C,M) hace que un nivel bajo limite el resultado y permite explicar compensaciones. No es una demostración de que todo crecimiento sea favorable. Se mantendrán los componentes y el contraste contra las series directas; la utilidad operativa requerirá evaluación posterior.

Se compararán 50/50, 60/40, 70/30 y 80/20, además de los extremos 0/100 y 100/0 como diagnósticos. Los controles y la regla de selección quedan fijados en protocolo.json. Una serie que falle cobertura no se rescata moviendo cortes o bajando mínimos. Un candidato que falle estabilidad no se declara cerrado por ajuste visual a una narrativa.

## Research de contexto: fuentes y límites

- BCRA, Informe Monetario diciembre de 2017, pp. 5 y 8–9: expansión y efecto de composición en tasas prendarias; aparición de UVA también en personales/prendarios. https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/Bol1217.pdf
- BCRA, diciembre de 2019, pp. 4–5: contracción prendaria y relación con actividad automotriz; descenso de personales. El deflactor de vehículos usado allí difiere de nuestro IPC nacional. https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/Bol1219.pdf
- BCRA, diciembre de 2020, pp. 5–7: asistencia durante pandemia y comportamientos distintos entre tarjetas, personales y prendarios; programas y plazos influyen. https://www.bcra.gob.ar/Pdfs/PublicacionesEstadisticas/Bol1220.pdf
- BCRA, diciembre de 2022: crédito real débil, prendarios con desempeño relativo diferente de consumo e hipotecarios. https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-diciembre-de-2022/
- BCRA, diciembre de 2023: caída real pronunciada del consumo y préstamos con garantía. https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-marzo-de-2024-2/
- BCRA, enero de 2024: persistencia de contracción real al inicio del año. https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-enero-de-2024/
- BCRA, agosto y diciembre de 2024: recuperación difundida, con diferencias de intensidad entre líneas. https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-agosto-de-2024/ ; https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-diciembre-2024/
- BCRA, septiembre de 2025: expansión del crédito ME junto con un contexto cambiario distinto del ML. https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-septiembre-de-2025/
- BCRA, junio de 2026: crecimiento real agregado pequeño y heterogéneo. https://www.bcra.gob.ar/publicaciones/informe-monetario-mensual-junio-de-2026/

Los informes suelen usar promedios mensuales, ajustes estacionales, correcciones contables y deflactores diferentes. Su dirección aporta contexto; sus magnitudes no se presentan como reconciliación exacta de nuestros saldos de cierre. Se conservan las diferencias entre líneas y episodios. Los datos anteriores a 2017 se incluyen en la auditoría/historia nominal, pero no se produce una historia real comparable con un IPC no disponible en este protocolo.

Para el contraste trimestral se utilizarán solo respuestas ECC observadas ponderadas: estándares, demanda, spread, montos y plazo. Para PH prendario, tarjetas y otros consumos se usará ECC Familias; otros consumos no equivale exactamente a personales. Para empresas, ECC general por tamaño es contexto de crédito amplio, no validación específica de prendarios ni de ME. No se utilizan respuestas esperadas ni se interpretan correlaciones como predicción.

Metodologías y accesos: https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/bolmetes.pdf (pp. 19–20 del PDF); https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/siscen.pdf (SISCEN-0011 y 0018); https://www.bcra.gob.ar/encuesta-condiciones-crediticias-ecc/ ; https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/ECC_Caracteristicas_y_formulario.pdf
