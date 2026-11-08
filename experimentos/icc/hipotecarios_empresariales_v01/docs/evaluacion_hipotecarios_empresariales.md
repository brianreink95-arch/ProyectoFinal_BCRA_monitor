# ICC hipotecario empresarial — evaluación 0.1
8 de octubre de 2026, Buenos Aires.

## Resultado
Se repitieron preparación, calibración S1, nueve sensibilidades y controles PCA1/FA1/PCA2 para hipotecarios ML a PyMEs (equivalente a 935) y No PyMEs (equivalente a 936). Ambos tienen 60 meses comunes de train, 22 de validación y 30 de retrospectiva. Ningún modelo supera todos los controles. S1 queda como **candidato experimental con proxy de tasa nominal**, no como ICC particular aprobado.

Se conservan dos segmentos: combinarlos antes de comprobar equivalencia escondería diferencias. No se recalculó el piloto PH927 ni se definió el global. Prestadoras929 y moneda extranjera quedan pendientes.

## Fuentes y ajuste de alcance
- Stock: BCRA, `perser_priv.xls`, hoja `Prest-Hip`, campos `pes_jur_otr_pyme` y `pes_jur_otr_res`. Snapshot oficial adquirido el 5/10/2026 a las 23:16 UTC, recuperado de la entrega previa. Se utiliza **la serie completa de este XLS** para el nuevo experimento; no se parchean dos meses de la API.
- Costo: BCRA, `preser_tas.xls`, hojas `Tasas_pers_jur_pymes` y `Tasas_pers_jur_otras`, columna física29 (índice desde cero), hipotecarios ML total de operaciones a tasa fija o repactable. Archivo descargado en esta evaluación, 9/10 UTC, 8/10 Buenos Aires.
- IPC: nacional INDEC, diciembre2016=100, versión conservada en `deflactor_ipc.csv`. No se usa empalme anterior.
- API: observaciones de consolidación `20261005_232225_036387`, únicamente para auditar equivalencia/revisiones; no para mezclar vintages.

La página oficial permite descargar tasas por tipo de titular. Las notas del XLS definen promedios ponderados por capital desembolsado para estas líneas. Esto mejora correspondencia de titular respecto de UVA1240, pero no resuelve todo: la tasa describe **flujo de operaciones fija/repactable**, el stock es **saldo vigente total ML**. Además, “otras personas jurídicas” necesita cotejo de población con No PyMEs del archivo de saldos; no se declara igualdad jurídica exacta.

La tasa nominal en pesos **no es comparable con TNA sobre UVA**. No se divide por IPC ni se llama tasa real. Cambios de inflación pueden alterar el nivel nominal sin el mismo cambio en costo real esperado. C es un descriptor relativo de tasa nominal de la modalidad publicada, no favorabilidad financiera integral ni CFT.

Fuentes oficiales:
- [Tasas de interés y descarga por titular](https://www.bcra.gob.ar/tasas-de-interes/)
- [XLS de tasas](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/preser_tas.xls)
- [Préstamos por tipo de titular](https://www.bcra.gob.ar/prestamos-y-otros-activos-de-las-entidades-financieras/)
- [XLS de saldos](https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/perser_priv.xls)

## Auditoría de unidad y discrepancias
El XLS expresa saldos en miles ARS. Se divide por1000 para millones ARS. Comparación con API: 319 meses emparejados por segmento; 317 coinciden dentro de0,501 millones, coherente con redondeo de la API. Los dos meses restantes presentan diferencias reales de desglose, no cambio de escala.

| Mes | Segmento | API, millones ARS | XLS, millones ARS | API menos XLS |
|---|---|---:|---:|---:|
| Mayo2026 | PyMEs | 681.322 | 683.305,765 | −1.983,765 |
| Junio2026 | PyMEs | 737.168 | 739.076,157 | −1.908,157 |
| Mayo2026 | No PyMEs | 223.219 | 221.235,203 | +1.983,797 |
| Junio2026 | No PyMEs | 244.336 | 242.427,791 | +1.908,209 |

Las diferencias casi se compensan entre titulares: es **compatible con una revisión/reclasificación**, sin evidencia para establecer su causa. `auditoria_api_xls.csv` conserva cada mes, no sólo discrepancias. No se alteran los originales ni se atribuyen nuevos desembolsos a esas diferencias.

## Features y calendario
Se calculan nivel real R, crecimiento1/3/12m, cambio absoluto3m, aceleración3m, volatilidad6m, tasa nominal y cambio3m. No se trasladan participaciones de destinos PH a empresas. Faltantes y guiones de tasas quedan nulos; cero observado permanece cero. Ventanas exigen meses consecutivos en calendario completo; no hay imputación, winsorización ni eliminación de extremos.

R=stock nominal millones × factor IPC; g=100(R/R[t−3]−1).
Core R/g3/r: marzo2017–junio2026.

| Bloque | Calendario | Core por segmento | Uso |
|---|---|---:|---|
| Train | Agosto2016–febrero2022 | 60 (marzo2017–febrero2022) | Ajustar referencias, escalas y modelos |
| Validación | Marzo2022–diciembre2023 | 22 | Controles congelados, sin refit |
| Retrospectiva | Enero2024–junio2026 | 30 | Aplicar luego de cerrar diagnóstico |
| Reserva | Desde julio2026 | Sin score | No habilitada |

No hay vintages para verificar disponibilidad histórica. La validación ya forma parte del trabajo exploratorio; no constituye un nuevo test intacto. Ninguna fecha posterior participa en calibración.

## Fórmula y pesos
Se retiene como **ancla de comparación**:
`B=100 V(0,80 C+0,20 M)`
`V=R/(R+R0); C=L((r0−r)/sr); M=L(g/sg)`.
L es logística; R0 y r0 son medianas de train; sr y sg=IQR/1,349, con pisos0,10 y0,50pp. Cada segmento se calibra por separado sobre los mismos60 meses comunes. Volumen no tiene un “peso20%”: es un factor multiplicativo. 80/20 pondera exclusivamente C/M. El punto R0/r0/g0 vale25, no neutralidad50.

| Referencia | PyMEs | No PyMEs |
|---|---:|---:|
| R0, millones ARS dic2016 | 9.771,5606 | 3.291,1172 |
| r0, TNA nominal % | 30,0350 | 31,6200 |
| sr, pp | 11,4956 | 13,9733 |
| sg, pp | 16,7898 | 8,1862 |

**Ajuste necesario:** reemplazar fuente/concepto de tasa y recalibrar referencias por segmento. No se encontró evidencia para elegir otros pesos. Se conservan80/20 provisionalmente para comparar con S1; no se afirma que sean óptimos ni económicamente validados. No se estiman pesos por PCA, varianza explicada o correlación con el propio baseline.

Se repitieron las nueve sensibilidades originales: pesos C/M100/0 y70/30; R0×0,75/1,25; escalas×0,75/1,25; crecimiento mensual; delta absoluto de saldo3m; cambio de tasa. **9/9 pasan en cada segmento**, con rho≥0,90 y MAE≤10 tanto en train como validación. Este control mide estabilidad alrededor del ancla; no valida la tasa ni determina pesos óptimos.

| Pesos C/M | PyMEs MAE val, puntos | PyMEs rho | No PyMEs MAE val | No PyMEs rho |
|---|---:|---:|---:|---:|
| 100/0 frente a80/20 | 3,1542 | 0,9718 | 1,6005 | 0,9785 |
| 70/30 frente a80/20 | 1,5771 | 0,9944 | 0,8003 | 0,9921 |

## Modelos y controles
Se reutilizan los mismos evaluadores numéricos del piloto, con adaptador explícito para validar calendario empresarial y mapear la tasa a la interfaz heredada. Las salidas públicas la llaman tasa hipotecaria nominal, nunca UVA. Se conserva el código de evaluadores en el paquete aislado; no reemplaza `ml/` del proyecto productivo.

| Método | PyMEs | No PyMEs |
|---|---|---|
| S1 | Economía y9 sensibilidades pasan | Economía y9 sensibilidades pasan |
| PCA1 | Falla reconstrucción | Falla perturbaciones y reconstrucción |
| FA1 | Falla dirección, perturbaciones y reconstrucción | Falla dirección, perturbaciones, reconstrucción y saturación |
| PCA2 | Falla reconstrucción2D | Falla reconstrucción2D |

PCA1 mejora MSE medio val18,03% en PyMEs, pero momentum tiene4,169× el error del comparador (>1,25). En No PyMEs mejora56,60%, pero volumen tiene14,323× y momentum1,297×. La mejora media no compensa pérdida excesiva de un input. Los JSON guardan todos los gates, parámetros, referencias y hashes. FA/PCA2 son diagnósticos adicionales; no se elige ganador después de inspeccionar los resultados.

**No se promueve S1 a ICC aprobado por fallback estadístico.** La equivalencia económica de la proxy y de la población sigue pendiente, aunque sus sensibilidades pasen.

## Ejemplo retrospectivo — junio2026
Valores del candidato nominal experimental, usando snapshot XLS coherente:

| Segmento | R, millones ARS dic2016 | TNA nominal | Crecimiento real3m | B |
|---|---:|---:|---:|---:|
| PyMEs | 6.249,3702 | 30,88% | +3,6869% | 19,3571 |
| No PyMEs | 2.049,8848 | 34,19% | +7,4830% | 19,4237 |

Son escalas relativas a historia propia: no permiten concluir que ambos segmentos tengan iguales condiciones ni compararlos directamente con PH. El score no se muestra al usuario final. Se conserva R, tasa y g3 para describir volumen y trayectoria sin depender de su agregación.

## Observabilidad y descomposición
Cada CSV incluye V/C/M, elegibilidad, motivos, split, segmento y estado experimental. Aportes al nivel: costo=100V×0,8C; momentum=100V×0,2M; suman B.

Para el cambio entre dos meses se usa descomposición simétrica exacta, con H=0,8C+0,2M:
- volumen:100 ΔV × promedio(H[t],H[t−1]);
- costo:100 promedio(V[t],V[t−1]) ×0,8 ΔC;
- momentum:100 promedio(V[t],V[t−1]) ×0,2 ΔM.

Los tres aportes suman ΔB, distribuyendo la interacción simétricamente. Son contribuciones algebraicas, no causas económicas. Los meses sin datos/reserva interrumpen el cambio; no se saltan huecos.

## Validación técnica y reproducibilidad
Ocho pruebas específicas comprueban: auditoría de revisiones; invariancia de referencias al alterar futuro; calendario continuo; falta de tasa sin imputación; reserva sin score; escenarios económicos; nombres sin UVA; reconciliación de nivel/cambio. Ejecución idéntica reproduce bytes de resultados. No se afirma haber corrido la suite completa histórica de141 pruebas en esta ampliación.

## Cierre y trabajo siguiente
1. Revisar definiciones jurídicas de “otras PJ” frente a936 y alcance de operaciones fija/repactable frente al saldo total.
2. Formalizar si la dimensión nominal describe condiciones de financiamiento o si se requiere una tasa real ex ante con expectativas compatibles. La inflación realizada puede servir como sensibilidad retrospectiva, no sustituir información disponible al cutoff.
3. Con esa decisión, fijar protocolo nuevo antes de cambiar pesos; hasta entonces mantener dos candidatos nominales separados y sus componentes.
4. Evaluar929 con su propia cobertura y proxy; no copiar tasas empresariales automáticamente. Después, completar hipotecarios ME y continuar otras familias.
5. El global sigue pendiente: no promediar estos scores con PH ni asignar pesos por stock sin definir universo, solapamientos y comparabilidad.

