# Plan y comparación de pesos del ICC hipotecario empresarial
15 de octubre de 2026 — exploración 0.2. Segmentos: PyMEs 935 y No PyMEs 936.

## Decisión de alcance
Se abre una comparación de ponderaciones, manteniendo la versión 0.1 como referencia cerrada. No se modifica el piloto de personas humanas, la tasa, las transformaciones, las escalas ni los cortes temporales. No se reemplazan los resultados publicados ni se habilita la reserva.

La pregunta es cuánto debe pesar la tasa nominal frente a la dinámica real para que el ICC sirva como señal descriptiva interna. No se trata de hacer que reproduzca el stock ni de encontrar pesos que imiten un relato histórico. El research anterior aporta contrastes externos al índice, con límites de población documentados.

## Fórmula y referencias congeladas
B(alpha)=100 V[alpha C+(1−alpha)M], alpha=peso del costo.
V conserva su función multiplicativa; no se le asigna un tercer porcentaje aditivo.
C es proxy de tasa nominal fija/repactable. M es crecimiento real trimestral transformado.
R0, r 0, sr y sg permanecen ajustados sobre los mismos 60 meses comunes de train de cada segmento.

Se evaluaron 11 valores de alpha:0,0;0,1;…;1,0. Los extremos son ablaciones: eliminan costo o momentum y no serían candidatos finales si el constructo exige ambas dimensiones.
El protocolo de esta comparación se guardó antes de ejecutar los cálculos; los datos y episodios ya habían sido examinados. Por tanto, esto sigue siendo exploratorio, no un experimento histórico pre-registrado ni un test intacto.

## Escenarios controlados ya calculados
Se generan 88 combinaciones:8 escenarios ×11 pesos. Se expresan relativamente a las referencias del segmento:
- Volumen R/R0:0,10;0,25;0,50;1 o 2.
- Costo favorable/desfavorable: tasa r 0−2sr/r 0+2sr, por lo que C≈0,881/0,119.
- Momentum expansivo/contractivo:g=+2sg/−2sg, por lo que M≈0,881/0,119.

Son escenarios de componentes, no historias económicas simuladas. Aislar R y g permite examinar la fórmula aunque esos inputs no sean independientes en una trayectoria real.

| Escenario | Costo/momentum 50/50 |60/40 |70/30 |80/20 |
|---|---:|---:|---:|---:|
| Stock R0, tasa baja y contracción |25,00 |28,81 |32,62 |36,42 |
| Stock R0, tasa alta y expansión |25,00 |21,19 |17,38 |13,58 |
| Rebote sobre base baja: R=0,25R0, tasa r 0, g=+2sg |13,81 |13,05 |12,28 |11,52 |
| Volumen alto: R=2R0, tasa r 0 y contracción |20,64 |23,18 |25,72 |28,26 |
| Volumen muy bajo y ambas condiciones buenas |8,01 |8,01 |8,01 |8,01 |

Cuando C=M, el peso no cambia el resultado: no se puede calibrar alpha con episodios donde todas las dimensiones coinciden. Con R=R0, C=M=0,5, todos producen 25; no es un umbral de neutralidad económica.

El 80/20 favorece marcadamente el escenario de tasa baja con contracción frente al de tasa alta con expansión.60/40 reduce esa compensación y conserva una preferencia moderada por el costo.50/50 empata ambos; no es automáticamente correcto por parecer balanceado.

## Contraste histórico ya calculado
Se mantienen los cortes exactos del research: contracción 2018, recuperación 2021, deterioro 2023, debilidad 2024-I, giro 2024-II y situación mixta 2026-II. Para 2026 no se inventa una dirección binaria, porque la ECC muestra mejoras y restricciones simultáneas.

Variación del candidato, en puntos, entre cierres del episodio:

| Segmento/episodio |50/50 |60/40 |70/30 |80/20 |
|---|---:|---:|---:|---:|
| PyMEs,2018: dic.2017→dic.2018 |−26,04 |−28,09 |−30,14 |−32,20 |
| No PyMEs,2018 |−28,36 |−30,08 |−31,81 |−33,53 |
| PyMEs,2021: dic.2020→dic.2021 |+14,75 |+14,18 |+13,61 |+13,03 |
| No PyMEs,2021 |+24,06 |+20,51 |+16,95 |+13,40 |
| PyMEs,2023: dic.2022→dic.2023 |−7,35 |−6,47 |−5,59 |−4,70 |
| No PyMEs,2023 |−4,28 |−4,39 |−4,51 |−4,63 |
| PyMEs,2024-II: mar.→jun.2024 |+10,33 |+11,52 |+12,70 |+13,89 |
| No PyMEs,2024-II |+21,19 |+20,18 |+19,17 |+18,17 |

Las principales alternativas reconocen esos giros. La historia seleccionada diferencia sobre todo **intensidades**, para las que no tenemos un puntaje externo equivalente que defina cuál es la magnitud correcta.

En 2024-I, No PyMEs cambia−0,44 puntos con 50/50,−0,28 con 60/40,−0,12 con 70/30 y+0,04 con 80/20. El umbral algebraico de cambio de signo es alpha≈0,7777. La variación con 80/20 es prácticamente plana: no se declara ganador a 70/30 por corregir ese signo mínimo, ni se introduce un umbral ex post para contabilizar “aciertos”.

Los archivos de resultados incluyen umbrales analíticos de alpha para cada episodio. No indican óptimos: muestran dónde cambia la dirección según esta fórmula y estos cierres.

## Ponderación nominal y efecto observado
La participación de cada componente en los movimientos depende también de cuánto varía. Sumar valores absolutos de las contribuciones simétricas al cambio y dividir por el total permite describir su influencia histórica. No es importancia causal ni descomposición de varianza.

| Segmento y pesos | Volumen | Costo | Momentum |
|---|---:|---:|---:|
| PyMEs 80/20 |12,35% |71,80% |15,85% |
| PyMEs 60/40 |13,68% |54,33% |31,99% |
| No PyMEs 80/20 |11,61% |55,98% |32,41% |
| No PyMEs 60/40 |10,32% |35,26% |54,43% |

Se usa marzo 2017–junio 2026 exclusivamente como diagnóstico retrospectivo. Pesos iguales no implican contribuciones efectivas iguales entre segmentos; bajar el costo a 60% no produce el mismo equilibrio empírico en ambos.

## Candidatos que conviene comparar
- **80/20:** referencia vigente; costo claramente prioritario.
- **70/30:** ajuste moderado; conserva bastante la interpretación original.
- **60/40:** candidato de trabajo para evaluar una mayor respuesta a la dinámica real y reducir la dependencia de una proxy nominal.
- **50/50:** referencia de equilibrio entre dimensiones, útil para inspeccionar compensaciones.

No se identifica un ganador histórico único.60/40 es una propuesta de criterio de diseño para contrastar, no un peso estimado como óptimo. No se adoptan todavía pesos distintos por segmento: aumentar parámetros sin evidencia de utilidad favorece el sobreajuste.

## Plancito para fijar los pesos
### 1. Fijar qué debe explicar el ICC
Definir el orden de importancia entre tasa nominal favorable, volumen real y dinámica real. Volumen conserva su límite multiplicativo. Acordar la lectura de casos conflictivos con ejemplos concretos: crédito con tasa baja pero contracción, crédito con tasa alta pero expansión y rebote sobre base pequeña.
**Salida:** criterio de compensación explícito, sin fijar puntajes absolutos inventados.

### 2. Mantener una comparación acotada
Comparar 50/50,60/40,70/30 y 80/20. Los 11 pesos calculados quedan como sensibilidad, no como búsqueda continua del máximo ajuste. Todas las alternativas usan la misma muestra y referencias.
**Estado:** escenarios y curvas ya generados.

### 3. Completar el contraste con ECC por dimensiones
Recuperar y validar el histórico completo de estándares, spreads, plazos, garantías y demanda, distinguiendo respuestas observadas de expectativas. Comparar cambios trimestrales del ICC con cada dimensión compatible; no equiparar niveles 0–100 con IDs−100/+100 ni dar a la ECC el papel de verdad absoluta.
Distinguir ECC empresas frente a hipotecarios empresariales y grandes empresas frente a No PyMEs. Una coincidencia con demanda no equivale a coincidencia con oferta.
**Salida:** matriz de concordancias y divergencias, sin entrenar todavía contra una etiqueta compuesta arbitraria.

### 4. Evaluar utilidad y estabilidad
Examinar las explicaciones de cada variante en los mismos episodios y en todos los trimestres disponibles; mostrar también casos discordantes. Revisar cuánto cambia la interpretación al mover ligeramente los cortes del episodio y al retirar un episodio completo. Es sensibilidad descriptiva sobre datos ya usados, no validación independiente.
Controlar continuidad, datos faltantes, saturación, influencia de componentes y estabilidad de las explicaciones. No premiar suavidad, correlación con 80/20 o mayor expansión por sí mismas.
**Salida:** candidatos no dominados y razones de descarte, si las hay.

### 5. Elegir por evidencia y criterio económico
Si una variante ofrece mejor correspondencia externa y explicaciones más útiles de forma estable, registrar la razón y sus límites. Si varias resultan indistinguibles, reconocer que los datos no identifican alpha: elegir una convención económica explícita con sensibilidad alrededor, en lugar de afirmar optimalidad.
La recomendación de trabajo es estudiar primero 60/40 y 70/30 contra 80/20, conservando 50/50 como control. La elección final debe justificar qué compensaciones acepta, especialmente mientras C siga siendo nominal.

### 6. Congelar y evaluar prospectivamente
Publicar una versión nueva con pesos, referencias, fuentes, criterios y fecha de decisión. Preservar 0.1. Mantener la reserva sin puntuar hasta aprobar un protocolo separado.
La evaluación operativa conserva el requisito previo de al menos 12 meses completos nuevos; no basta con reajustar pesos retrospectivos ni sustituir el período por unas pocas observaciones.
**Salida:** pesos adoptados para el uso definido, con seguimiento; no garantía causal ni de acceso.

## Validación y reproducción de esta entrega
El script verifica que 80/20 reproduce el candidato original y que los aportes al cambio reconcilian en las 22 combinaciones segmento/peso. Conserva los nulos y la reserva de los CSV originales. Dos ejecuciones deben producir los mismos resultados.

Desde esta carpeta:
```bash
python -m pip install numpy pandas scipy
python comparar_pesos.py
```

Incluye protocolo JSON, los dos CSV de entrada congelados,8 escenarios,6 episodios por segmento,11 pesos, trayectorias, métricas, contribuciones, umbrales y hashes. No extrae fuentes, no refitea referencias ni modifica el pipeline de producción.

Contexto histórico: `research_historico_icc_hipotecarios_empresariales.md`, con 18 fuentes oficiales consultadas. Esta comparación reutiliza ese research; no es un nuevo relevamiento externo ni cambia sus limitaciones.

