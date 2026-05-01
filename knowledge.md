# Análisis del Sistema Recomendador

A continuación se detalla la respuesta a cada una de las preguntas planteadas tras analizar el código y la documentación técnica del proyecto.

## Implementación

**¿Cómo se ha dividido el dataset?**
Se ha dividido de forma aleatoria asignando un **70% de los datos como conjunto de Entrenamiento** (utilizado para generar los perfiles de usuario y calcular afinidades) y un **30% como conjunto de Test** (aislado estrictamente para evaluar la bondad de la predicción y precisión del recomendador).

**Para los usuarios del dataset:**
- **¿Cómo se han obtenido las preferencias de los usuarios?**
  A partir de las calificaciones dadas en el histórico de entrenamiento. El proceso asume que si un usuario califica una película con valor $r$ y esta pertenece a $k$ géneros, esa película aporta de manera equitativa una fracción $r/k$ a cada uno de sus géneros.
- **¿Cómo se ha creado el perfil de los usuarios?**
  Agregando estas fracciones calculadas se crea un vector de preferencias de 20 dimensiones (por los 20 géneros disponibles en el dataset) para cada usuario. Seguidamente, este vector se normaliza con un método Min-Max, quedando todos los valores escalados en el rango $[0, 1]$.

**Para los usuarios nuevos:**
- **¿Cómo se obtienen sus preferencias?**
  A través de un modal (interfaz gráfica) creado en la aplicación web (`app.py`), donde los usuarios sin historial ("Cold Start") pueden puntuar explícitamente/manualmente sus géneros de interés. Este perfil se ingesta para ejecutar cualquiera de los modelos bajo demanda.

---

## SR Basado en Contenido

**¿Cuál es el proceso de recomendación?**
1. **Filtrado de preferencias:** Se ordena el vector del usuario de mayor a menor y se seleccionan, como máximo, los 5 géneros principales, aplicando una regla de "truncado dinámico".
2. **Obtención de candidatas:** Se seleccionan todas las películas que no estén en el historial del usuario y que compartan *al menos un género* con las preferencias seleccionadas.
3. **Cálculo de score:** Se calcula una puntuación para cada candidata con una fórmula específica.
4. **Ranking:** Se ordenan las candidatas según este score y se devuelve el Top N (Top 10 normalmente).

**¿En qué se basa y qué datos usa? ¿Qué preferencias se usan?**
Se basa en inferir el gusto por ítems no vistos analizando las similitudes con ítems que sí le han gustado. Emplea el vector normalizado de preferencias del usuario y los metadatos de las películas (géneros, puntuación media de la comunidad y recuento de votos). Se utilizan exclusivamente los géneros del **top 5 seleccionados** que logran superar el truncado dinámico.

**Explicar cualquier decisión de diseño:**
- **Truncado dinámico:** Se aplica un filtro que descarta géneros si se detecta un "salto brusco" (ej. una caída relativa de más del $30\%$ respecto al género anterior). Esto evita introducir ruido por géneros que se hayan votado marginalmente.
- **Factor de fiabilidad logarítmica:** Se implementó una penalización para castigar aquellas películas que tienen una alta puntuación media pero provienen de muy pocos votos de la comunidad, evitando recomendar ítems anómalos.

**¿Cómo se ha calculado el ratio de un ítem usando las preferencias con las que está clasificado? ¿Y si el ítem está clasificado en más de una preferencia?**
La fórmula utilizada es: $r(u,i) = \alpha \cdot \text{Afinidad} + \beta \cdot \text{Calidad} + \gamma \cdot \text{Fiabilidad}$ (pesos por defecto: $\alpha=0.50$, $\beta=0.30$, $\gamma=0.20$).
Para el componente de Afinidad, se calcula la suma del grado de preferencia del usuario en los géneros que coinciden entre la película y el vector filtrado, dividida entre la suma total de las preferencias del vector filtrado. 
Si el ítem está clasificado en más de un género afín, **su afinidad aumenta de forma aditiva**, ya que se suman en el numerador los valores de interés del usuario para todos esos géneros coincidentes, logrando cubrir una mayor "proporción" de los intereses del usuario.

---

## SR Colaborativo

**Proceso de obtención de vecinos:**
- **Cómo se ha realizado:** Se ha implementado un enfoque *Usuario-Usuario*. En lugar de crear una matriz esparsa inmensa con las puntuaciones de las películas, se utiliza el vector de preferencias de géneros de 20 dimensiones (Preferencias por Unión, llenando con ceros los géneros no informados en el historial).
- **Cómo se ha calculado el ratio de afinidad de cada vecino:** Mediante el **Coeficiente de Correlación de Pearson**, calculando la similitud vectorial entre los perfiles de 20 dimensiones.
- **¿Límite en el nº de vecinos?:** Sí, el sistema acota la vecindad quedándose solo con el **Top-K de vecinos**, fijado en un máximo de **40**.

**Proceso de obtención de la lista de ítems recomendados:**
- **Cálculo del ratio de interés de cada ítem:** Tras descartar las películas que el usuario solicitante ya ha visto y quedarse con las películas valoradas favorablemente (ej. >= 3.0) por sus vecinos, se calcula una media ponderada: se multiplican las calificaciones de los vecinos por su respectiva similitud (Pearson), y se divide por la suma absoluta de las similitudes involucradas.
- **Qué ocurre cuando un ítem proviene de más de un vecino:** Sus valoraciones **se combinan en la media ponderada**. En el numerador se suman los productos de `similitud * puntuación` aportados por cada vecino que ha visto ese ítem, y el denominador crece agregando los valores absolutos de esa similitud. Esto otorga mayor peso al voto de los vecinos que se parecen más al usuario.

---

## SR Híbrido

**¿Técnica híbrida usada?**
Se utiliza una técnica de **Híbrido Ponderado (Weighted Hybrid)** que mezcla y unifica los resultados de los enfoques Basado en Contenido (CB) y Colaborativo (CF).

**Cálculo del ratio del ítem:**
El ratio final es: $r(u,i)_{Hibrido} = \alpha \cdot r(u,i)_{CB} + \beta \cdot r(u,i)_{CF}$, donde $\alpha$ y $\beta$ son dinámicos y suman $1$.
La puntuación aportada por el SR Colaborativo (que tiene un rango de 0.5 a 5.0) **se normaliza al rango $[0,1]$** para ser equitativa respecto a la del modelo de contenido, que ya se mueve en ese rango.

**¿Qué ocurre cuando el ítem aparece en la lista de ítems recomendados de más de un recomendador?**
Se fusionan sus puntajes ponderando cada uno con los coeficientes $\alpha$ y $\beta$. Si la película aparece solo en uno de los dos sistemas, su puntuación para el sistema en el que falta asume el valor $0$ (se aplica una penalización). Las constantes $\alpha$ y $\beta$ no son estáticas, sino que se recalibran según un nivel de **confianza**: el perfilado de géneros pesa más si el vector es fuerte (alto $\alpha$), y la parte colaborativa pesa más si los vecinos encontrados tienen una correlación promedio alta (alto $\beta$).

---

## Recomendación para Grupos

**Técnica usada para combinar las recomendaciones:**
Se implementa una fase estricta de exclusión inicial donde se descarta del catálogo **todo ítem que se encuentre en el historial de AL MENOS UN miembro** del grupo, garantizando la novedad para todos. A partir de aquí, las listas individuales se integran utilizando diversas técnicas de agregación y consenso:
- **Average (Media):** Promedio directo de los scores.
- **Borda Count (Posición de Ranking):** Se otorgan puntos según el puesto que ocupa la película en la lista top individual de cada miembro (la 1ª recibe $N-1$ puntos, la 2ª $N-2$, etc.).
- **Least Misery (Mínima Miseria):** Toma en cuenta el score más bajo emitido por un miembro, previniendo recomendar cosas fuertemente repudiadas por alguien.
- *Otras extra:* Plurality Voting, Approval Voting, Multiplicativa y "Dictatorship" (Donde priman las preferencias del usuario más experimentado).

**Cálculo del ratio del ítem para el grupo:**
Depende de la técnica escogida. Por ejemplo, en *Least Misery*, el score final grupal de la película es directamente el valor mínimo de entre todos los scores pre-calculados por los miembros. En *Average*, el ratio del ítem para el grupo es la suma de los $r(u,i)$ individuales dividida por la cantidad de personas del grupo. 

---

## Interfaz

**¿Qué información se muestra?**
La interfaz presenta:
- El Top 10 de recomendaciones finales dependiendo del algoritmo seleccionado (Contenido, Colaborativo, Híbrido, Grupos).
- Al pedir recomendaciones por grupo, se visualiza el ratio del grupo junto al desglose de los *scores* individuales (estrellas) que aportó cada miembro al consenso.
- Detalles del vector de preferencias (gráficas y representaciones en radar que comparan un vector genérico contra el truncado).
- Alerta al usuario si no hay datos suficientes ("Cold Start").

**Aspectos diferentes o mejoras que habéis incluido, algún extra:**
1. **Solución a "Cold Start" para Nuevos Usuarios:** Inclusión de un Modal o formulario interactivo para registrar preferencias manualmente y convertirlas on-the-fly en un vector virtual para recomendaciones inmediatas.
2. **Llamadas a la API de TMDB:** Extensión de la información mostrada para traer de manera asíncrona pósters carátula originales, la sinopsis argumental (overview), y el reparto de actores de las películas a través de consultas reales al API de "The Movie Database".
3. **Pre-computado y Evaluación (Métricas visuales):** Se ha habilitado un endpoint para leer archivos pre-calculados con evaluación estadística (`global_metrics.json`), facilitando la comparación de Precision@10 y MAE entre los modelos sin bloquear el sistema web.
4. **Pre-computado de Item-Item CF:** Se calcula la similitud con técnicas vectorizadas al arrancar el backend permitiendo resolver consultas en tiempos muy bajos.
