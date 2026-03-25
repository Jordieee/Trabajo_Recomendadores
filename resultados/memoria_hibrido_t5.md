# Memoria de Implementación: Sistema Recomendador Híbrido (Trabajo 5)

## 1. Diseño y Arquitectura del Recomendador Híbrido Ponderado
El sistema recomendador híbrido se ha implementado como una función que orquesta y combina (mediante una estrategia ponderada) los resultados provenientes de los dos sistemas base:
1. **Sistema Recomendador Basado en Contenido (T3)**
2. **Sistema Recomendador Colaborativo (T4 - Usuario-Usuario)**

### Cómo funciona el algoritmo de hibridación:
Cuando un usuario solicita una recomendación híbrida, el sistema realiza los siguientes pasos en `trabajo5_sr_hibrido.py`:
1. **Generación de candidatos**: Se solicitan todas las recomendaciones posibles (no solo el Top 10) al recomendador de contenido y al colaborativo Usuario-Usuario de forma independiente. Ambos sistemas ya han excluido las películas que el usuario ya ha visto (histórico del usuario).
2. **Ponderación Dinámica (Cálculo de $\alpha$ y $\beta$)**: Se evita usar un ratio fijo estático. Los valores exactos se determinan al vuelo en función de la "seguridad" o "calidad" de la información de la que disponemos para el usuario:
   * **Confianza de Contenido ($\alpha$)**: Calculada a partir de los perfiles de preferencias generados en el T3. Se verifica cuántos géneros de preferencia tiene el usuario y los valores normalizados con los que conectan. Cuanto más estructurado está el perfil, mayor es el valor bruto de esta confianza.
   * **Confianza Colaborativa ($\beta$)**: Calculada a base del promedio de la similitud positiva de los $N$ vecinos más próximos del usuario actual (Pearson). Si las distancias de Pearson demuestran una alta similitud con el clúster de vecinos, esta confianza es alta.
   * Finalmente, se normalizan ambos valores brutos para asegurar el requerimiento teórico principal: $\alpha + \beta = 1$.
   * *Caso extremo:* Si un usuario acaba de entrar al sistema y no tiene ningún vecino pero sí rellenó algunos géneros, $\beta$ será $0$ y $\alpha$ absorberá todo el coeficiente ponderador al $100\%$, actuando temporalmente como Content-Based puro hasta que reciba interacciones. Lo mismo ocurriría si no hay vector de preferencias pero sí hay vecinos (aunque es estadísticamente menos común).
3. **Fusión de Rankings y Ratios**: Se crea un diccionario unificado donde quedan indexadas por ID todas las películas candidatas, ya vengan de uno o de ambos extractores. Para cada película candidata $i$ se calcula su nuevo ratio $r_{(u,i)}$ como:
   $$ r_{(u,i)} = \alpha \cdot r_{(cont)} + \beta \cdot r_{(collab)} $$
   *NOTA:* Ambos ratios individuales fueron previamente normalizados en una escala comparable entre $0$ y $1$ (por ejemplo, el rating del colaborativo de entre $0.5$ y $5.0$ estrellas se divide entre $5$ para lograr un valor comparable al score interno del T3).

## 2. Decisiones de Interfaz de Usuario
Se han añadido selectores dentro de la pantalla gráfica principal (`templates/index.html` y `static/js/main.js`) que permiten saltar en caliente entre las distintas lógicas implementadas (T3 vs T4 vs T5). Esto cumple la meta experimental de testar las comparativas con un solo click.

Para la recomendación híbrida en particular, las tarjetas de películas devueltas (Top 10):
* Muestran el identificador de la(s) lista(s) matriz de donde salieron (etiquetas de "Contenido" y/o "Colaborativo" coloreadas en la película).
* Desglosan a nivel píxel los puntajes pre-procesados para transparentar cuánto porcentaje específico de similitud vino dictado por qué métrica original antes de ponderarse en la suma final de estrellas.
* Se informa la balanza exacta calculada para $\alpha$ y $\beta$ de la sesión en el panel resumen.

## 3. Pruebas y Simulaciones
**Usuario Test Existente vs Usuario Nuevo:**
* Como podemos observar al arrancar un usuario nativo del dataset original con historial abundante, tanto el SR de Contenido como el Colaborativo entregan buenas métricas de confianza internas originando valores equilibrados donde $\alpha \approx 0.55$ y $\beta \approx 0.45$. En este ecosistema, la fusión de scores extrae las películas más aclamadas intercediendo al milímetro con las desviaciones del gusto.
* Si insertáramos un usuario de "Arranque en Frío" de escaso historial, el sistema es robusto, equilibrando los fallos del Cold Start del colaborativo balanceando $\alpha \to 1.0$ de facto hasta asimilar histórico social con sus co-visores, erradicando los temidos recomendadores vacíos.
