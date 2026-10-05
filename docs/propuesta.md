# Propuesta de Proyecto Final — Observatorio de Financiamiento y Endeudamiento en Argentina

## 1. Título provisional

**Observatorio de Financiamiento y Endeudamiento en Argentina: integración, análisis y modelado de datos financieros públicos**

## 2. Descripción general

El proyecto propone desarrollar una aplicación web que centralice, procese y visualice información pública y actualizada sobre el acceso al financiamiento y el nivel de endeudamiento en Argentina.

La plataforma buscará facilitar la comprensión de cómo se financian distintos actores de la economía —familias, PyMEs y empresas— integrando fuentes actualmente distribuidas entre diferentes organismos públicos.

El Banco Central de la República Argentina será la fuente principal de información. Actualmente dispone de APIs públicas para Central de Deudores, Estadísticas Monetarias, Estadísticas Cambiarias y Régimen de Transparencia, entre otras.

La aplicación tendrá un foco particular en:

- evolución del crédito en Argentina;
- alternativas de financiamiento disponibles;
- endeudamiento empresarial;
- condiciones crediticias;
- préstamos personales;
- préstamos prendarios;
- tarjetas de crédito;
- **créditos hipotecarios**.

El objetivo final no será solamente desarrollar un análisis estático, sino construir un sistema que continúe incorporando nuevos datos automáticamente y permita consultar el estado actualizado del mercado crediticio argentino.

## 3. Problema

La información sobre crédito y financiamiento en Argentina se encuentra distribuida entre distintos organismos, publicaciones, datasets y sistemas de consulta.

Esto dificulta responder de forma rápida preguntas como:

- ¿Cómo está evolucionando el endeudamiento de las familias?
- ¿Qué tipos de crédito están creciendo?
- ¿Qué condiciones ofrecen actualmente las entidades financieras?
- ¿Qué alternativas hipotecarias existen?
- ¿Cómo evoluciona el endeudamiento de una empresa determinada?
- ¿Qué empresas presentan deterioro o mejoras en su situación crediticia?
- ¿Cómo se financian las PyMEs fuera del sistema bancario?
- ¿Cómo cambian las tasas, los montos y las condiciones de financiamiento a lo largo del tiempo?

El proyecto busca resolver este problema mediante la construcción de una capa de integración y análisis que transforme distintas fuentes públicas en información homogénea, histórica y consultable desde una única aplicación.

## 4. Pregunta principal

**¿Cómo pueden integrarse y analizarse fuentes públicas y actualizadas para construir una visión unificada del financiamiento y endeudamiento de familias, PyMEs y empresas en Argentina?**

Como componente específico de Ciencia de Datos se investigará además cómo transformar datos financieros públicos y actualizados en indicadores derivados que sinteticen condiciones de mercado, comparen alternativas de financiamiento y detecten señales de estrés empresarial.

**¿Es posible utilizar técnicas de Machine Learning para generar métricas actualizables y accionables que ayuden a interpretar el mercado crediticio y apoyar la toma de decisiones?**

## 5. Objetivo general

Desarrollar una plataforma web de análisis financiero que integre datos públicos del sistema financiero argentino, conserve su evolución histórica y permita explorar las alternativas y dinámicas de endeudamiento de familias, PyMEs y empresas.

## 6. Objetivos específicos

1.  Integrar automáticamente las APIs públicas del BCRA.

2.  Construir pipelines de ingesta y transformación para almacenar periódicamente la información obtenida.

3.  Generar una base histórica propia a partir de fuentes que publican información actualizada.

4.  Construir indicadores que permitan analizar la evolución del crédito, tasas, deuda y condiciones financieras.

5.  Desarrollar un módulo orientado a familias que permita analizar productos financieros disponibles.

6.  Desarrollar un módulo específico de **créditos hipotecarios**, permitiendo comparar condiciones entre entidades.

7.  Incorporar información de personas jurídicas reales utilizando identificadores societarios públicos.

8.  Desarrollar fichas de empresas que permitan visualizar su evolución de endeudamiento y situación crediticia.

9.  Desarrollar tres indicadores derivados mediante técnicas de Machine Learning: condiciones crediticias, atractivo relativo de productos financieros y estrés financiero empresarial.

10. Implementar y desplegar la solución utilizando servicios cloud con el objetivo de mantener un **costo operativo de \$0** durante el desarrollo académico.

## 7. Fuentes de datos

### Banco Central de la República Argentina

Será la principal fuente de información.

Se utilizarán inicialmente:

**API de Estadísticas Monetarias**

Permitirá consultar series históricas relacionadas con:

- préstamos;
- depósitos;
- tasas;
- variables monetarias;
- indicadores financieros;
- evolución general del sistema crediticio.

La versión vigente publicada por el BCRA es Estadísticas Monetarias v4.0.

API de Estadísticas Cambiarias

Permitirá incorporar cotizaciones y evolución de monedas como variables de contexto para interpretar condiciones financieras y enriquecer los indicadores derivados.

**API de Régimen de Transparencia**

Permitirá consultar condiciones actuales de productos financieros ofrecidos por las entidades.

Entre ellos:

- préstamos personales;
- hipotecarios;
- prendarios;
- tarjetas;
- depósitos;
- otros productos bancarios.

La API fue publicada específicamente para facilitar la integración de esta información en aplicaciones externas.

**API Central de Deudores**

Permitirá consultar información pública sobre financiaciones informadas al BCRA para un CUIT determinado.

Para este proyecto, el análisis masivo se limitará a **personas jurídicas**.

### Registro Nacional de Sociedades

Se utilizará como posible fuente del universo de empresas argentinas.

El Registro permite identificar personas jurídicas mediante CUIT/CDI y razón social y publica además una base completa para su descarga.

La combinación:

**Registro Nacional de Sociedades → CUIT → Central de Deudores BCRA**

permitirá construir un dataset de empresas reales y analizar su situación de endeudamiento.

### Comisión Nacional de Valores

Como segunda etapa se evaluará incorporar información de la CNV para representar alternativas de financiamiento fuera del crédito bancario.

La CNV publica estadísticas sobre:

- Obligaciones Negociables;
- Cheques de Pago Diferido;
- Pagarés;
- Facturas de Crédito Electrónicas;
- financiamiento PyME por instrumento;
- fideicomisos financieros.

Esta integración se considera inicialmente una **extensión del MVP**, para evitar ampliar excesivamente el alcance inicial.

## 8. Aplicación web

La aplicación estará organizada inicialmente en cuatro módulos.

### Panorama

Visión general del crédito argentino:

- evolución del crédito;
- tasas;
- composición del financiamiento;
- indicadores de mora;
- tendencias recientes.

### Familias

Información relacionada con:

- préstamos personales;
- tarjetas;
- prendarios;
- hipotecarios;
- condiciones actuales ofrecidas por entidades.

Los datos individuales de personas físicas no formarán parte del dataset del proyecto.

### Hipotecarios

Será uno de los principales verticales funcionales.

Permitirá analizar y comparar:

- entidades;
- tasas;
- plazos;
- montos máximos;
- condiciones de acceso;
- relación cuota/ingreso;
- evolución histórica de las ofertas.

La captura periódica de las condiciones publicadas permitirá además construir un histórico propio de productos hipotecarios.

### Empresas

Permitirá buscar y analizar personas jurídicas reales.

Una ficha empresarial podrá mostrar, según disponibilidad:

- razón social;
- CUIT;
- evolución de deuda;
- entidades acreedoras;
- situación crediticia;
- atrasos;
- evolución mensual;
- indicadores derivados.

Posteriormente podrá enriquecerse con información de financiamiento proveniente del mercado de capitales.

## 9. Componente de Ciencia de Datos

El Machine Learning se utilizará como una capa de generación de señales sobre la información integrada por la plataforma. El objetivo no será producir predicciones aisladas, sino transformar datos financieros crudos en métricas comparables y actualizables que ayuden a interpretar el estado del crédito y a tomar decisiones informadas. La actualización de cada indicador respetará la frecuencia efectiva de las fuentes utilizadas.

Se proponen tres indicadores principales. La selección final de variables, hiperparámetros y algoritmos se realizará luego del análisis exploratorio y de la validación de calidad de los datos.

### 9.1 Índice de Condiciones Crediticias y Momentum

**Objetivo.** Sintetizar en una única métrica el grado de expansión o restricción del crédito argentino y su dirección reciente, diferenciando cuando sea posible personas humanas, PyMEs, empresas y crédito hipotecario.

APIs que lo alimentarán:

- Estadísticas Monetarias v4.0: stock de préstamos por tipo de titular y línea, tasas de interés, depósitos, variables monetarias e indicadores crediticios.
- Estadísticas Cambiarias: cotizaciones y evolución del tipo de cambio como variables de contexto.
- Régimen de Transparencia: agregados derivados de la oferta vigente, como cantidad de productos activos, tasas y costos financieros publicados por las entidades.

Variables candidatas:

- variaciones mensuales y trimestrales del stock de crédito;
- tasas nominales y efectivas;
- participación de cada línea de crédito;
- cantidad de entidades y productos disponibles;
- variación de condiciones de oferta;
- volatilidad y momentum de las series;
- variables monetarias y cambiarias de contexto.

Algoritmos/modelos a considerar:

- PCA o métodos equivalentes de reducción dimensional para construir factores sintéticos a partir de múltiples series correlacionadas;
- K-Means o Gaussian Mixture Models para identificar regímenes de condiciones crediticias;
- Hidden Markov Models como alternativa para modelar transiciones temporales entre regímenes expansivos, neutrales y restrictivos;
- reglas de normalización y percentiles históricos como baseline interpretable.

**Output esperado.** Un score normalizado de 0 a 100, acompañado por una etiqueta de régimen (expansivo, neutral o restrictivo), una tendencia reciente y una comparación contra percentiles históricos.

**Integración visual.** Tarjeta principal en el módulo Panorama con score, etiqueta y variación respecto del período anterior; serie temporal del índice; tarjetas por segmento —personas, PyMEs, empresas e hipotecarios— y señalización de cambios de régimen.

### 9.2 Índice de Atractivo Relativo de Productos Financieros

**Objetivo.** Comparar una oferta crediticia contra productos similares del mercado y estimar si sus condiciones se encuentran por encima o por debajo de lo esperable para su tipo, monto, plazo y requisitos.

APIs que lo alimentarán:

- Régimen de Transparencia: préstamos hipotecarios, personales, prendarios y tarjetas de crédito; incluirá TEA, CFTEA, plazo, monto, ingreso mínimo, relación cuota/ingreso, relación monto/tasación y demás condiciones disponibles.
- Estadísticas Monetarias v4.0: tasas de referencia y series históricas para contextualizar el nivel general de tasas.
- Estadísticas Cambiarias y variables UVA/CER disponibles en las fuentes del BCRA cuando correspondan al producto analizado.

Algoritmos/modelos a considerar:

- Regresión Lineal Regularizada / Elastic Net como baseline;
- Random Forest Regressor;
- Gradient Boosting / XGBoost para estimar el costo esperado de una oferta a partir de sus características;
- modelos por tipo de producto cuando la heterogeneidad entre hipotecarios, personales y prendarios lo justifique.

**Métrica derivada.** El costo observado de cada producto —principalmente CFTEA o TEA según disponibilidad— se comparará con el costo esperado por el modelo. El residual y el percentil relativo dentro del mercado se transformarán en un score de atractivo de 0 a 100.

**Output esperado.** Para cada producto: score de atractivo, percentil de costo, diferencia respecto del costo esperado y posición relativa frente a productos comparables. El score será descriptivo y comparativo, no una recomendación financiera personalizada.

**Integración visual.** Ranking y comparador de productos; badge de atractivo en cada tarjeta; gráfico de producto vs. mercado comparable; filtros por entidad, monto, plazo y tipo de crédito. En el vertical hipotecario se utilizará como una de las métricas principales para ordenar y explorar ofertas.

### 9.3 Índice de Estrés Financiero Empresarial

**Objetivo.** Detectar comportamientos crediticios atípicos o señales de tensión en personas jurídicas a partir de la evolución de su deuda y su relación con las entidades acreedoras, sin depender necesariamente de una etiqueta supervisada de default.

APIs que lo alimentarán:

- Central de Deudores: histórico por CUIT, montos informados, situación crediticia, entidades acreedoras, revisión y proceso judicial.
- Central de Deudores - Cheques Rechazados: señal adicional cuando existan registros asociados a la empresa.
- Estadísticas Monetarias v4.0: variables macro y crediticias de contexto para distinguir movimientos propios de una empresa de cambios generales del sistema.

Features candidatas:

- deuda total y variación mensual;
- cantidad de entidades acreedoras;
- concentración de deuda por entidad;
- situación crediticia máxima y promedio;
- cambios de situación;
- aparición de revisión o proceso judicial;
- cheques rechazados cuando estén disponibles;
- desvío de la empresa respecto de su propio historial y del contexto agregado.

Algoritmos/modelos a considerar:

- Isolation Forest como candidato principal para detección de anomalías multivariadas;
- Local Outlier Factor y One-Class SVM como alternativas de comparación;
- clustering para construir grupos de comportamiento crediticio y comparar una empresa contra pares;
- un modelo supervisado de deterioro futuro —por ejemplo Regresión Logística o Gradient Boosting— sólo como extensión si el volumen y balance de clases resultan suficientes.

**Output esperado.** Un score de estrés de 0 a 100 por empresa y período, acompañado por tendencia, posición relativa y variables que más contribuyen a la señal. El índice no se interpretará como probabilidad de default ni como calificación crediticia oficial.

**Integración visual.** Dentro de la ficha de empresa se mostrará el score actual, su evolución en los últimos 24 meses, eventos relevantes y principales factores asociados al cambio. El buscador empresarial podrá permitir ordenar o filtrar empresas por nivel de estrés cuando el volumen de datos lo permita.

### 9.4 Validación de los indicadores

Los tres índices se validarán de acuerdo con la naturaleza de cada problema. Para los modelos de regresión se considerarán MAE, RMSE y R²; para clustering y regímenes se evaluarán estabilidad, separación e interpretabilidad; y para detección de anomalías se estudiará estabilidad temporal, revisión de casos extremos y, si existen etiquetas posteriores, métricas de discriminación. Todos los índices se compararán contra baselines simples para verificar que la complejidad del modelo agregue información útil.

La plataforma conservará la versión del modelo y los datos utilizados para generar cada score, permitiendo reproducibilidad, actualización periódica y monitoreo de drift cuando se incorporen nuevas observaciones.

## 10. Arquitectura tecnológica preliminar

La solución seguirá una arquitectura desacoplada:

**Fuentes públicas → Ingesta → Almacenamiento Cloud → Transformación → Modelos/Índices → API propia → Web App**

### Ingesta

Procesos programados consultarán periódicamente las fuentes públicas.

### Almacenamiento

Se conservarán dos niveles principales:

- datos crudos provenientes de las fuentes;
- datos procesados y normalizados.

El almacenamiento permitirá conservar snapshots históricos aunque la fuente original solamente exponga el estado actual.

### Backend

Una API propia centralizará el acceso de la aplicación a los datos procesados, indicadores derivados y metadatos de los modelos utilizados.

### Frontend

Se desarrollará una aplicación web responsive orientada principalmente a:

- exploración;
- visualización;
- comparación;
- búsqueda de empresas;
- análisis de productos financieros.

### Cloud

Se priorizarán tecnologías:

- serverless;
- free tier;
- open source;
- bases PostgreSQL o equivalentes;
- almacenamiento de objetos;
- ejecución programada de pipelines.

La selección definitiva de proveedores se realizará considerando que el costo mensual del proyecto académico debe mantenerse en **\$0**.

## 11. Alcance inicial

Para evitar un alcance excesivo, el MVP se limitará inicialmente a:

1.  Integración BCRA.
2.  Base histórica propia.
3.  Panorama general de crédito.
4.  Productos financieros para familias.
5.  Comparador de hipotecarios.
6.  Consulta y análisis de empresas.
7.  Tres indicadores derivados mediante Machine Learning integrados a la aplicación.
8.  Aplicación web desplegada.

La incorporación completa de CNV será considerada una segunda fase.

También quedarán fuera del alcance inicial:

- scraping de portales inmobiliarios;
- asistentes basados en LLM;
- recomendaciones financieras personalizadas;
- datos crediticios masivos de personas físicas.

Estos componentes podrán incorporarse posteriormente sin modificar la arquitectura central.

## 12. Plan de trabajo

### Etapa 1 — Descubrimiento y validación de datos

- testear APIs del BCRA;
- relevar variables disponibles;
- evaluar calidad y cobertura histórica;
- descargar muestra del Registro Nacional de Sociedades;
- validar cruce de empresas con Central de Deudores;
- definir dataset inicial;
- definir variables, baselines y metodología de cálculo de los tres indicadores.

### Etapa 2 — Ingeniería de datos

- desarrollar conectores;
- definir schemas;
- almacenar información;
- desarrollar procesos de actualización;
- normalizar fuentes;
- generar diccionario de datos.

### Etapa 3 — Análisis exploratorio

- analizar distribución y calidad;
- detectar valores faltantes;
- estudiar evolución temporal;
- analizar correlaciones;
- caracterizar empresas y productos;
- evaluar factibilidad, estabilidad e interpretabilidad de los indicadores propuestos.

### Etapa 4 — Modelado

- construir features para los tres indicadores;
- definir baselines interpretables para cada índice;
- entrenar y comparar los modelos candidatos;
- validar desempeño, estabilidad temporal e interpretabilidad;
- normalizar los outputs y definir escalas 0-100;
- integrar los scores y explicaciones en la API y la interfaz web.

### Etapa 5 — Desarrollo de producto

- desarrollar backend;
- desarrollar frontend;
- integrar visualizaciones;
- implementar buscador;
- desarrollar vista de hipotecarios;
- desarrollar fichas empresariales.

### Etapa 6 — Cloud y automatización

- desplegar servicios;
- programar ingestas;
- automatizar actualizaciones;
- almacenar nuevos snapshots;
- ejecutar inferencias cuando corresponda.

### Etapa 7 — Documentación y entrega

- documentar arquitectura;
- documentar datasets;
- documentar metodología;
- presentar resultados;
- preparar defensa.

## 13. Cronograma

### Hasta el 02/09 — Hito 1

- definición formal del problema;
- validación técnica de fuentes;
- diseño preliminar de arquitectura;
- selección inicial de variables;
- plan de trabajo;
- cronograma.

### 03/09 al 23/09 — Hito 2

- implementación de ingesta inicial;
- construcción del dataset;
- almacenamiento;
- análisis exploratorio;
- diccionario de datos;
- validación definitiva de variables, baselines y estrategias de modelado para los tres índices.

### 24/09 al 21/10 — Hito 3

- feature engineering para índices de condiciones crediticias, atractivo de productos y estrés empresarial;
- entrenamiento, comparación y evaluación de los modelos candidatos;
- construcción del backend;
- primera versión funcional de la web;
- definición y calibración de scores 0-100;
- validación de estabilidad e interpretación de señales;
- interpretación de resultados.

### 22/10 al 11/11 — Entrega Final

- refactorización;
- automatización de pipelines;
- despliegue cloud;
- testing;
- documentación técnica;
- notebook reproducible;
- informe final.

### Noviembre — Defensa

- preparación de presentación;
- demostración de la aplicación;
- integración visual de índices y factores explicativos;
- preparación de defensa individual.

## 14. Resultado esperado

Al finalizar el proyecto se espera contar con una aplicación web funcional que permita consultar y analizar información actualizada del financiamiento argentino, incorporando índices derivados que sinteticen condiciones crediticias, atractivo relativo de productos y señales de estrés empresarial.

A diferencia de un análisis estático, la solución estará diseñada para continuar incorporando nuevos datos y conservar su historia.

El proyecto combinará:

**Ciencia de Datos + Data Engineering + Cloud + Desarrollo Web**

con el objetivo de transformar información financiera pública dispersa en una herramienta concreta y reutilizable.
