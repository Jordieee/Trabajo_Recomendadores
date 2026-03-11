import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path('Data_set')
RESULT_DIR = Path('resultados')

# Load necessary data
df_ratings = pd.read_csv(DATA_DIR / 'ratings_small.csv', sep=';', decimal=',')
df_peliculas = pd.read_csv(DATA_DIR / 'peliculas.csv', sep=';', encoding='utf-8-sig', decimal=',')
id_to_titulo = dict(zip(df_peliculas['id'], df_peliculas['titulo']))

df_pref_norm = pd.read_csv(RESULT_DIR / 'user_genre_matrix_normalized.csv', sep=';', decimal=',', index_col='userId')
df_pref_union = df_pref_norm.fillna(0.0)

rating_matrix = df_ratings.pivot_table(index='userId', columns='movieId', values='rating', aggfunc='mean')

def pearson_cor(u1, u2):
    # Vectorized computation of Pearson on df_pref_union
    u1_v = u1 - u1.mean()
    u2_v = u2 - u2.mean()
    num = (u1_v * u2_v).sum()
    den = np.sqrt((u1_v**2).sum()) * np.sqrt((u2_v**2).sum())
    return num / den if den != 0 else np.nan

def recomendar_usuario_usuario_preferencias(user_id: int, k_vecinos=20, n_rec=10, sim_minima=0.1):
    if user_id not in df_pref_union.index:
        return {'error': 'User not found in preference matrix.'}
    
    u_pref = df_pref_union.loc[user_id]
    
    similitudes = {}
    # Computar Pearson con todos
    # Se puede optimizar con numpy
    prefs_np = df_pref_union.values
    means = prefs_np.mean(axis=1, keepdims=True)
    centered = prefs_np - means
    norms = np.linalg.norm(centered, axis=1)
    
    u_idx = df_pref_union.index.get_loc(user_id)
    u_centered = centered[u_idx]
    u_norm = norms[u_idx]
    
    for i, other_id in enumerate(df_pref_union.index):
        if other_id == user_id: continue
        if norms[i] == 0 or u_norm == 0: continue
        sim = np.dot(u_centered, centered[i]) / (u_norm * norms[i])
        if not np.isnan(sim) and sim >= sim_minima:
            similitudes[other_id] = float(sim)
            
    if not similitudes:
        return {'error': 'No neighbors found'}
        
    top_vecinos = sorted(similitudes.items(), key=lambda x: x[1], reverse=True)[:k_vecinos]
    sim_dict = dict(top_vecinos)
    vecinos_ids = list(sim_dict.keys())
    
    u_ratings = rating_matrix.loc[user_id] if user_id in rating_matrix.index else pd.Series(dtype=float)
    peliculas_vistas = set(u_ratings.dropna().index)
    
    predicciones = []
    # Peliculas valoradas por los vecinos
    # ratings de los vecinos
    vecinos_ratings = rating_matrix.loc[vecinos_ids]
    
    for movie_id in vecinos_ratings.columns:
        if movie_id in peliculas_vistas:
            continue
            
        ratings_for_movie = vecinos_ratings[movie_id].dropna()
        if ratings_for_movie.empty:
            continue
            
        # Filtrar solo vecinos que hayan puntuado "favorablemente" (ej. >= 3.0) para recomendar
        ratings_for_movie = ratings_for_movie[ratings_for_movie >= 3.0]
        if ratings_for_movie.empty:
            continue
            
        num = 0.0
        den = 0.0
        valid_neighbors = 0
        
        for v_id, r_vi in ratings_for_movie.items():
            sim_v = sim_dict[v_id]
            num += sim_v * r_vi
            den += abs(sim_v)
            valid_neighbors += 1
            
        if den > 0:
            pred_rating = num / den
            predicciones.append({
                'movieId': int(movie_id),
                'titulo': id_to_titulo.get(movie_id, str(movie_id)),
                'pred_rating': round(pred_rating, 3),
                'sim_avg': round(den / valid_neighbors, 3),
                'n_vecinos': valid_neighbors
            })
            
    predicciones.sort(key=lambda x: x['pred_rating'], reverse=True)
    return {
        'recomendaciones': predicciones[:n_rec],
        'vecinos': [{'userId': int(v), 'similitud': round(s, 3)} for v, s in top_vecinos[:10]]
    }

user_test = 5 # Example user
print("Testing UU Pref for user 5")
res = recomendar_usuario_usuario_preferencias(user_test)
print(res)
