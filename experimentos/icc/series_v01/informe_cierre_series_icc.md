# Implementación del plan de series pendientes del ICC

Versión pendientes 0.1 — 15 de octubre de 2026. Corte analítico: junio de 2026. Uso descriptivo interno.

## Resultado

Se ejecutó la auditoría de los 17 stocks pendientes y se incorporaron cuatro stocks específicos de personales/tarjetas (ML y ME). Se exploraron todas las familias antes de calcular candidatos. Las 21 series evaluadas en esta entrega quedan clasificadas: cuatro ICC experimentales, nueve indicadores parciales, siete series de contexto y una exclusión/diferimiento. Los tres ICC hipotecarios anteriores se preservan y llevan el total disponible a siete ICC experimentales; estos no tienen niveles directamente comparables.

Se implementaron extracción local de XLS, auditoría API/XLS, conversión ME, features, exploración por época, escenarios, referencias de train, controles, contraste ECC, atribuciones y registro de decisiones. Las salidas están en resultados/ y los scripts se pueden volver a ejecutar sin red. No se incorporaron al sitio ni se habilitaron alertas. El global tiene un acta explícita de bloqueo, no una fórmula improvisada.

## Nuevos ICC experimentales

| Serie y alcance | Costo/momentum | Meses con score | Junio 2026 |
| --- | --- | --- | --- |
| Prendarios PH ML | 50/50 | 112 | 38.84 |
| Prendarios PyMEs ME | 50/50 | 112 | 46.31 |
| Personales ML · privado | 60/40 | 112 | 17.05 |
| Tarjetas ME · privado | 60/40 | 112 | 57.16 |

Todos tienen 60 meses comunes de train, 22 de validación y 30 de retrospectiva: marzo de 2017–junio de 2026. Las cifras de la última columna usan referencias propias: no permiten ordenar segmentos por mejores condiciones absolutas.

Fórmula: B = 100 × V × [αC + (1−α)M]. V = R/(R+R₀); C = logística((r₀−r)/sᵣ); M = logística(g3/sɢ). El volumen multiplica la combinación costo/dinámica. R₀ y r₀ son medianas del train común; las escalas usan IQR/1,349, con pisos explícitos. En ML, R está en millones de ARS de diciembre de 2016; en ME, R está en millones de USD equivalentes nominales. La tasa es nominal y parcial, no CFT ni costo real.

Los pesos se eligieron con una regla fijada antes del cálculo: evaluar 50/50 como convención inicial y, si falla estabilidad, 60/40, 70/30 y 80/20, en ese orden. Se adopta el primero que supera todos los controles; si ninguno pasa, no se cierra un ICC. Se compararon también 0/100 y 100/0 como diagnósticos. No se maximizó la correlación histórica ni se encontró un óptimo estadístico. El protocolo es una extensión experimental con ponderaciones propias; no sustituye los controles ni las decisiones de los modelos anteriores.

Prendarios PH ML y PyMEs ME pasan con 50/50. Personales ML y tarjetas ME necesitan 60/40 bajo esa regla: 50/50 falla la sensibilidad que cambia crecimiento trimestral por mensual. Pasar controles algebraicos y de estabilidad no demuestra validez integral del constructo económico.

## Candidatos que no se cerraron como ICC

| Serie | Sensibilidades con fallos | Decisión |
| --- | --- | --- |
| Prendarios PyMEs ML | costo_0.8_nivel_0.2_delta_tasa, g1_en_lugar_g3 | Ningún peso evaluado pasa todo |
| Prendarios No PyMEs ML | costo_0.8_nivel_0.2_delta_tasa, g1_en_lugar_g3 | Ningún peso evaluado pasa todo |
| Tarjetas ML · privado | costo_0.8_nivel_0.2_delta_tasa, g1_en_lugar_g3 | Ningún peso evaluado pasa todo |

Estos tres segmentos tienen datos completos, pero un cambio razonable de feature altera demasiado el orden temporal del puntaje. En No PyMEs prendarios ML, por ejemplo, la correlación al sustituir g3 por g1 llega a 0,457 para 50/50; ni 80/20 alcanza 0,90 en esa sensibilidad. No se eliminó el control después de ver ese resultado. Se conservan todos los escenarios y se publica un indicador parcial de volumen/dinámica.

Los hipotecarios ME 938, 946 y 947 tienen respectivamente 37, 53 y 35 meses completos de train, frente a los 60 requeridos. Prendarios ME PH 971 tiene 59: no se rebajó el mínimo ni se movió el calendario para incluirlo. Prendarios ME No PyMEs 980 tiene 21. El volumen es utilizable y permite IVD; falta soporte suficiente para el costo en S1.

Para prestadoras, 962 tiene stock utilizable pero no una tasa específica: queda IVD. 929 queda como contexto por cobertura y costo; 973 también, por intermitencia y referencia insuficiente. 940 se excluye/difiere para el protocolo reciente: publica cero en los 115 meses diciembre de 2016–junio de 2026, a la precisión del XLS. Esto no demuestra ausencia económica por debajo de la precisión publicada. Personales ME queda como contexto por escasez de saldo y tasa. Los cuatro totales por titular quedan como exposición y contexto.

IVD = 100 × R/(R+R₀) × logística(g3/sɢ), con sus propias referencias de train y mínimos 60/18. No tiene costo y no es intercambiable con el ICC. Las nueve salidas parciales tienen referencias y flags; no se completaron sus tasas para hacerlas pasar.

## Auditoría y tratamiento de moneda

Se cotejaron 20 stocks con 319 meses cada uno contra el XLS, incluyendo los tres anteriores como controles de fuente. La unidad del XLS es miles de ARS y se convierte a millones. La API tiene redondeo y algunas revisiones: las diferencias se conservan en auditoria_api_xls.csv. El nuevo experimento usa íntegro el snapshot XLS, sin mezclar API y XLS por conveniencia. Las salidas previas no se reescriben.

La mayor precisión importa: 929 tiene 32 ceros en el XLS en el período reciente frente a 41 en API. Recuperar saldos pequeños no resuelve por sí solo la viabilidad de un índice. Los faltantes, ceros y discrepancias de tasas/montos tienen flags separados.

Para ME se identificó la regla oficial de conversión y se utilizó A3500 de cierre, con fecha de observación conservada y control de antigüedad. Se produjeron saldo en USD equivalentes y descomposición exacta del cambio ARS en volumen, tipo de cambio e interacción. Esto remueve la valuación ARS/USD; no elimina otras paridades ni convierte el saldo en poder de compra real argentino. El stock medio de finserprom ME se toma directamente en USD equivalentes; no se multiplica por un tipo de cambio promedio para fabricar una exposición ARS media.

Una tasa publicada positiva con monto redondeado cero se conserva con flag; una tasa cero sin monto positivo no se interpreta como financiamiento gratuito. Las capturas tienen fechas distintas y no son vintages históricos contemporáneos. En algunas hojas hay cabeceras españolas genéricas: se verificó el universo con el nombre de hoja y su cabecera inglesa específica. El mapeo queda en catalogo_auditado.csv y en las features.

Se conservaron residuales de total menos ML/ME. En el período reciente llegan a aproximadamente −1,06%/+0,52% en prendarios por titular, por encima del mero redondeo. No se les asigna una causa única ni se fuerza la identidad. Los totales no se suman otra vez a sus subproductos.

## Lectura por época

La exploración completa está en exploracion_inicial.md, con diez informes históricos oficiales y las metodologías. Los números de este apartado provienen de nuestras propias series sin desestacionalizar; la comparación con informes BCRA es contextual y no una reconciliación exacta de magnitudes.

- **2017:** expansión de prendarios y personales; el costo de prendarios también depende de composición y modalidades. No se hereda automáticamente el episodio UVA hipotecario.
- **2018–2019:** contracción real fuerte en prendarios ML y personales; ME tiene otra trayectoria. Los pesos no se ajustaron para imponer el mismo signo a todas las monedas.
- **2020–2021:** la pandemia y la asistencia producen comportamientos distintos entre productos y titulares. El hueco de 1215 se conserva; 1220 se utiliza como otra proxy, no como imputación de 1215.
- **2022–2023:** pérdida de volumen real en gran parte del consumo y costo nominal alto; la heterogeneidad prendaria empresarial permanece visible. Una tasa nominal relativa no equivale a tasa real.
- **Inicio de 2024:** caída adicional de saldos reales. La expansión posterior parte de bases bajas y puede generar un momentum alto sin recomponer niveles anteriores.
- **Resto de 2024 y 2025:** recuperación de varias líneas, con diferentes intensidades y niveles; conservar el detalle evita confundir mejora de dinámica con condiciones históricamente altas.
- **Primer semestre de 2026:** señales mixtas. En PH prendarios ML el índice sube pese a caer el saldo real; en ME tarjetas la baja de la tasa domina la mejora del índice. La explicación debe explicitar esas compensaciones.

| Serie | Cambio ICC dic.2025–jun.2026 | Aporte volumen | Aporte costo | Aporte momentum |
| --- | --- | --- | --- | --- |
| Prendarios PH ML | +16.45 | -1.20 | +15.23 | +2.41 |
| Prendarios PyMEs ME | +18.74 | +2.08 | +7.01 | +9.65 |
| Personales ML · privado | +0.92 | -0.42 | +1.81 | -0.47 |
| Tarjetas ME · privado | +19.87 | +0.83 | +18.00 | +1.05 |

Los aportes son una identidad simétrica de la fórmula y suman exactamente el cambio. No son una estimación causal. Por ejemplo, la mejora de 16,44 puntos del prendario PH ML incluye un aporte de volumen negativo y un aporte de costo fuertemente positivo. Describirlo como mejora generalizada del crédito ocultaría lo observado en el stock.

## Contraste externo y consistencia histórica

Se extrajeron las respuestas ECC observadas ponderadas de familias y se amplió el contraste empresarial con montos máximos. Se emparejaron 37 cambios entre cierres trimestrales, 2017-II–2026-II, para cuatro ponderaciones por cada uno de los siete candidatos completos y cinco dimensiones por candidato. Las respuestas esperadas no se usan. La ECC no es una etiqueta de verdad del ICC ni un objetivo supervisado.

| Serie | Trimestres | ρ demanda | ρ estándares | ρ spread |
| --- | --- | --- | --- | --- |
| Prendarios PH ML | 37 | +0.373 | +0.145 | +0.242 |
| Prendarios PyMEs ME | 37 | +0.152 | -0.074 | +0.158 |
| Personales ML · privado | 37 | +0.578 | +0.425 | +0.565 |
| Tarjetas ME · privado | 37 | -0.114 | +0.060 | -0.163 |

Personales ML muestra el contraste más favorable entre los nuevos índices, aunque otros consumos de la ECC no coincide exactamente con personales. Para prendarios PH ML la relación con demanda es positiva, pero la de estándares es débil. Para prendarios PyME ME el benchmark es crédito empresarial amplio por tamaño, sin equivalencia de línea/moneda; para tarjetas ME el benchmark de hogares tampoco separa ME y muestra asociaciones débiles o negativas. Estos dos últimos no quedan validados como resúmenes de las condiciones completas por superar los controles numéricos.

Se revisaron neutralidad ECC de ±5, bandas de cambio ICC 0,5/1/2, exclusión de cada año y cierres ±1 mes, sin usar reserva. La sensibilidad al cierre es material: en prendarios PH ML la correlación con demanda pasa de 0,373 a 0,068 al desplazar el cierre un mes hacia adelante. No se eligió el corte más favorable ni se afirma consistencia histórica universal. La revisión aporta evidencia y límites, no predicción o causalidad.

## Registro de cierre por serie

La cobertura principal es core ICC train/validación. Para IVD se informa además su cobertura propia; un cero de cobertura de costo no significa ausencia de historia de volumen. Las filas existentes solo registran el cierre previo.

| Serie | Familia | Titular | Moneda | Estado | Meses train/validación |
| --- | --- | --- | --- | --- | --- |
| 927 | Hipotecarios | PH | ML | existente_cerrado | 60/22 |
| 929 | Hipotecarios | Prestadoras | ML | contexto | 0/0 |
| 935 | Hipotecarios | PyMEs | ML | existente_cerrado | 60/22 |
| 936 | Hipotecarios | No_PyMEs | ML | existente_cerrado | 60/22 |
| 938 | Hipotecarios | PH | ME | indicador_parcial | 37/12; IVD 60/22 |
| 940 | Hipotecarios | Prestadoras | ME | excluida_diferida | 0/0 |
| 946 | Hipotecarios | PyMEs | ME | indicador_parcial | 53/21; IVD 60/22 |
| 947 | Hipotecarios | No_PyMEs | ME | indicador_parcial | 35/0; IVD 60/22 |
| 960 | Prendarios | PH | ML | ICC_experimental | 60/22 |
| 962 | Prendarios | Prestadoras | ML | indicador_parcial | 0/0; IVD 60/22 |
| 968 | Prendarios | PyMEs | ML | indicador_parcial | 60/22; IVD 60/22 |
| 969 | Prendarios | No_PyMEs | ML | indicador_parcial | 60/22; IVD 60/22 |
| 971 | Prendarios | PH | ME | indicador_parcial | 59/22; IVD 60/22 |
| 973 | Prendarios | Prestadoras | ME | contexto | 0/0 |
| 979 | Prendarios | PyMEs | ME | ICC_experimental | 60/22 |
| 980 | Prendarios | No_PyMEs | ME | indicador_parcial | 21/3; IVD 60/22 |
| 883 | Total | PH | MEyML | contexto | 0/0 |
| 885 | Total | Prestadoras | MEyML | contexto | 0/0 |
| 891 | Total | PyMEs | MEyML | contexto | 0/0 |
| 892 | Total | No_PyMEs | MEyML | contexto | 0/0 |
| finserprom_personales_ml_privado | Personales | Privado | ML | ICC_experimental | 60/22 |
| finserprom_personales_me_privado | Personales | Privado | ME | contexto | 2/0 |
| finserprom_tarjetas_ml_privado | Tarjetas | Privado | ML | indicador_parcial | 60/22; IVD 60/22 |
| finserprom_tarjetas_me_privado | Tarjetas | Privado | ME | ICC_experimental | 60/22 |

## Global y trabajo restante

El registro de las 21 series evaluadas está resuelto para esta versión, pero el ICC global no está cerrado. El acta decision_global.json enumera los bloqueos: referencias propias sin equivalencia demostrada; ML real frente a ME nominal USD; mezcla de promedios mensuales y cierres; solapamiento de totales/subproductos; líneas comerciales no cubiertas y residuales sin conciliación completa.

La arquitectura mantiene dos caminos: una partición homogénea por productos o una por titulares, sin sumar ambas. Antes de calcular se deben fijar significado común, calibración comparable, pesos, cobertura mínima y tratamiento de ausencias. No se ofrece un promedio de los siete índices como si fuera el crédito argentino. No se renormalizan pesos ni se rellenan ausencias con cero.

Para reabrir los candidatos fallidos corresponde investigar la sensibilidad de la dinámica, estacionalidad, composición y definición de costo bajo otro protocolo explícito. No seguir probando pesos sobre los mismos datos hasta conseguir un resultado aceptable. La integración técnica, utilidad de las explicaciones y validación prospectiva son etapas posteriores, separadas de este cierre descriptivo.

## Verificación y reproducción

Pasaron 10 pruebas metodológicas. Dos ejecuciones independientes reprodujeron 144 archivos CSV/JSON sin diferencias. Las pruebas incluyen precisión, calendario, conversión ME y atribuciones, referencias sin datos futuros, rechazo del train de 59 meses, reserva sin score, huecos, rango, contribuciones, controles y ECC. Los CSV empresariales previos 935/936 se cotejaron con el ZIP anterior y permanecen idénticos.

El entorno verificado está en entorno_verificado.json y las dependencias en requirements.txt. Uso: python ejecutar.py --fase todo --output DIRECTORIO_NUEVO; luego python validar.py --output DIRECTORIO_NUEVO. generar_informe.py reconstruye este informe desde resultados/. Los originales están en fuentes/, con hashes en procedencia_eda.json y procedencia_modelos.json. No hay descargas implícitas al ejecutar.

## Archivos para revisar

- graficos/nuevos_icc_stock_tasa_indice.png: los cuatro nuevos ICC, con stock, tasa y pesos.
- graficos/eda_*.png: exploración de las cinco familias.
- resultados/registro_decisiones.csv: decisión y fundamento por serie.
- resultados/indices/: los cuatro ICC; resultados/parciales/: los nueve IVD.
- resultados/controles_escenarios.csv: controles económicos por serie/peso.
- resultados/candidatos/: trayectorias regenerables al ejecutar el experimento completo.
- resultados/sensibilidades.csv, contraste_ecc.csv, robustez_ecc.csv y pares_ecc_icc.csv: evidencia del contraste y sus divergencias.
- resultados/epocas_stock_tasa.csv y epocas_indices.csv: cambios por época de todas las series/candidatos.
- exploracion_inicial.md: investigación inicial y fuentes oficiales; protocolo.json: reglas previas.
