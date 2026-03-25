import numpy as np
import pandas as pd
from trabajo3_sr_contenido import (
    recomendar_contenido, df_pref_norm, df_ratings_valid,
    pelicula_generos, df_peliculas, V_REF
)
from trabajo4_sr_colaborativo import recomendar_usuario_usuario

def recomendar_hibrido(user_id: int, n_recomendaciones: int = 10):
    """
    Sistema Recomendador Híbrido Ponderado.
    Mezcla las recomendaciones del SR Basado en Contenido y del SR Colaborativo.
    """
    # 1. Obtener todas las recomendaciones posibles de ambos sistemas
    res_cont = recomendar_contenido(
        user_id, df_pref_norm, df_ratings_valid,
        pelicula_generos, df_peliculas, V_REF,
        n_top_genres=5, umbral_salto=0.30,
        n_recomendaciones=10000, verbose=False
    )
    
    res_col = recomendar_usuario_usuario(
        user_id, k_vecinos=40, n_recomendaciones=10000
    )
    
    # Manejar posibles errores
    error_cont = False
    if isinstance(res_cont, tuple):
        df_cont, pref = res_cont
    else:
        df_cont, pref = pd.DataFrame(), pd.Series(dtype=float)
        
    if df_cont.empty:
        error_cont = True
        
    error_col = False
    if 'error' in res_col:
        error_col = True
        vecinos = []
        df_col = pd.DataFrame()
    else:
        vecinos = res_col.get('vecinos', [])
        df_col = pd.DataFrame(res_col['recomendaciones'])
    
    if error_cont and error_col:
        return {"error": "No se pudieron obtener recomendaciones ni por contenido ni colaborativas."}
        
    # 2. Calcular Alpha y Beta dinámicamente
    # Calidad de contenido (basado en número de géneros fuertes y sus valores)
    conf_cont = 0.0
    if not error_cont and not pref.empty:
        # Suma de las preferencias seleccionadas (max ~ 1.0)
        conf_cont = min(1.0, pref.sum() / 1.5)  # Heurística
        # Si tiene preferencias, aseguramos un mínimo de confianza
        conf_cont = max(0.2, conf_cont)
        
    # Calidad colaborativa (basado en la similitud promedio de los vecinos)
    conf_col = 0.0
    if not error_col and vecinos:
        sims = [v['similitud'] for v in vecinos if v['similitud'] > 0]
        if sims:
             conf_col = np.mean(sims) # La similitud de Pearson ya está en [0, 1]
    
    # Si alguno no tiene confianza, el otro toma el 100%
    if conf_cont == 0 and conf_col == 0:
        return {"error": "No hay confianza suficiente para realizar la recomendación."}
    
    # Normalizamos alpha y beta para que sumen 1
    total_conf = conf_cont + conf_col
    alpha = conf_cont / total_conf
    beta = conf_col / total_conf
    
    # 3. Mezclar los ítems
    # Diccionario para unificar: movie_id -> {datos}
    items_mixtos = {}
    
    if not df_cont.empty:
        for _, row in df_cont.iterrows():
            mid = int(row['movieId'])
            items_mixtos[mid] = {
                'movieId': mid,
                'titulo': row['titulo'],
                'puntuacion': row['puntuacion'],
                'score_cont': row['score_final'], # Ya en [0, 1]
                'score_col': 0.0,
                'en_cont': True,
                'en_col': False
            }
            
    if not df_col.empty:
        for _, row in df_col.iterrows():
            mid = int(row['movieId'])
            # pred_rating está en [0.5, 5.0]. Lo normalizamos a [0, 1] dividiendo entre 5.0
            s_col = row['pred_rating'] / 5.0
            if mid in items_mixtos:
                items_mixtos[mid]['score_col'] = s_col
                items_mixtos[mid]['en_col'] = True
            else:
                items_mixtos[mid] = {
                    'movieId': mid,
                    'titulo': row['titulo'],
                    'puntuacion': row.get('puntuacion', 0.0), # Extraer puntuacion de la película si existe
                    'score_cont': 0.0,
                    'score_col': s_col,
                    'en_cont': False,
                    'en_col': True
                }
                
    # 4. Calcular ratio híbrido
    resultados = []
    for mid, data in items_mixtos.items():
        # r_{ui} = alpha * r_{cont} + beta * r_{col}
        # Si un ítem no está en una de las listas, su score en esa es 0
        r_hibrido = alpha * data['score_cont'] + beta * data['score_col']
        
        resultados.append({
            'movieId': data['movieId'],
            'titulo': data['titulo'],
            'puntuacion': data['puntuacion'],
            'score_hibrido': round(r_hibrido, 4),
            'score_cont': round(data['score_cont'], 4),
            'score_col': round(data['score_col'], 4),
            'en_cont': data['en_cont'],
            'en_col': data['en_col']
        })
        
    # Ordenar por el score híbrido
    resultados.sort(key=lambda x: x['score_hibrido'], reverse=True)
    
    return {
        "recomendaciones": resultados[:n_recomendaciones],
        "preferencias": {str(k): float(v) for k, v in pref.items()} if not pref.empty else {},
        "vecinos": vecinos,
        "alpha": round(alpha, 3),
        "beta": round(beta, 3)
    }
